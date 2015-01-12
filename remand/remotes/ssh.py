from binascii import hexlify
from functools import wraps
from threading import Thread
import os

import click
from paramiko.client import (SSHClient, AutoAddPolicy, RejectPolicy,
                             MissingHostKeyPolicy)
from paramiko.ssh_exception import SSHException, BadHostKeyException
from six.moves import shlex_quote

from . import Remote, RemoteProcess, _validate_umask
from .. import config, log
from ..exc import TransportError, RemoteFailureError

_KNOWN_HOSTS_ERROR = (
    "The host '{}' was not found in your known_hosts file. "
    "Remand is refusing to connect to unknown hosts.\n\n"
    "If you have an older version of Paramiko installed, this may be because "
    "of a key-type mismatch.\n\n"
    "See https://github.com/paramiko/paramiko/pull/473 for more information.")


_BAD_KEY_ERROR = (
    "The remote host's key does not match the key in your known_hosts file.\n"
    # for extra drama, we copy the openssh error message
    "IT IS POSSIBLE THAT SOMEONE IS DOING SOMETHING NASTY!\n\n"
    "Remote host key: {} {}\n"
    "known_hosts key: {} {}\n\n"
    "The host key for '{}' has changed and checking is enabled."
)


class WarnAutoAddPolicy(AutoAddPolicy):
    def missing_host_key(self, client, hostname, key):
        log.warning('Missing hostkey for {} ignored (fingerprint is {}).'
                    .format(hostname, format_key(key)))
        return super(WarnAutoAddPolicy, self).missing_host_key(
            client, hostname, key
        )


class AskToAddPolicy(MissingHostKeyPolicy):
    _UNKNOWN_WARNING = (
        "The authenticity of host '{}' can't be established.\n"
        "{} key fingerprint is {}."
    )
    _USER_PROMPT = "Are you sure you want to continue connecting?"

    def missing_host_key(self, client, hostname, key):
        click.echo(self._UNKNOWN_WARNING.format(
            hostname, key.get_name(), format_key(key),
        ))
        if not click.confirm(self._USER_PROMPT):
            raise TransportError('User declined to connect to unknown host')


class AskToSavePolicy(AskToAddPolicy):
    _USER_PROMPT = (
        "Are you sure you want to save to known_hosts and continue?"
    )

    def missing_host_key(self, client, hostname, key):
        super(AskToSavePolicy, self).missing_host_key(client, hostname, key)

        # add, this does not save it though
        client._host_keys.add(hostname, key.get_name(), key)

        if client._host_keys_filename is not None:
            client.save_host_keys(client._host_keys_filename)
            log.info('Added {} host key for {}: {}'.format(
                key.get_name(), hostname, format_key(key)
            ))
        else:
            log.warning('Did not save host, no known_hosts file loaded.')


def format_key(key):
    return ':'.join(hexlify(b) for b in key.get_fingerprint())


def ssh_host_name(uri):
    if uri.port is None or uri.port == 22:
        return uri.host
    else:
        return '[{0.host}]:{0.port}'.format(uri)


def wrap_ssh_errors(f):
    @wraps(f)
    def _(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except SSHException, e:
            raise TransportError('SSH ({}): {}'.format(
                type(e).__name__, e.message))
    return _


def wrap_sftp_errors(f):
    @wraps(f)
    def _(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except IOError, e:
            fargs = ', '.join(
                list(args[1:]) + ['{}={}'.format(*v) for v in kwargs]
            )
            raise RemoteFailureError('SFTP Failed {}({}): {}'.format(
                f.__name__, fargs, str(e)))
    return wrap_ssh_errors(_)


class SSHRemoteProcess(RemoteProcess):
    def __init__(self, stdin, stdout, stderr):
        self.stdin = stdin
        self.stdout = stdout
        self.stderr = stderr

    @property
    def _channel(self):
        return self.stdin.channel

    def poll(self):
        if self._channel.exit_status_ready():
            # ensure that a finished process always has an exit status
            self.returncode = self._channel.recv_exit_status()
            return True

    def wait(self):
        self.returncode = self._channel.recv_exit_status()

    def communicate(self, input=None):
        def read_thread(src, buffer):
            buffer.append(src.read())

        stdout = []
        stderr = []

        stdout_thread = Thread(target=read_thread, args=(self.stdout, stdout))
        stderr_thread = Thread(target=read_thread, args=(self.stderr, stderr))

        stdout_thread.setDaemon(True)
        stderr_thread.setDaemon(True)

        stdout_thread.start()
        stderr_thread.start()

        if input is not None:
            self.stdin.write(input)
            log.debug('Input sent')
        self.stdin.close()

        # wait for stdout/stderr to finish
        stdout_thread.join()
        stderr_thread.join()

        self.stdout.close()
        self.stderr.close()

        self.wait()
        return (stdout[0], stderr[0])


class _ShutdownWrap(object):
    def __init__(self, channelfile, shutdown_how):
        self._channelfile = channelfile
        self._shutdown_how = shutdown_how

    def close(self):
        self._channelfile.close()
        self._channelfile.channel.shutdown(self._shutdown_how)

    def __getattr__(self, key):
        return getattr(self._channelfile, key)


class SSHRemote(Remote):
    uri_prefix = 'ssh'

    __sftp = None

    @wrap_ssh_errors
    def __init__(self):
        self._client = SSHClient()

        # load known_hosts
        for kh_path in config['load_known_hosts'].split(os.pathsep):
            path = os.path.expanduser(kh_path)
            if not path:
                continue
            if not os.path.exists(path):
                log.warning('Skipping non-existant known_hosts file: {}'
                            .format(path))
                continue
            log.debug('Loading SSH known hosts from {}'.format(path))
            self._client.load_host_keys(path)

        on_missing_host_key = config['on_missing_host_key']
        policy = RejectPolicy()
        if on_missing_host_key == 'ignore':
            policy = WarnAutoAddPolicy()
        elif on_missing_host_key == 'ask':
            policy = AskToAddPolicy()
        elif on_missing_host_key == 'ask_to_save':
            policy = AskToSavePolicy()

        log.debug('Missing host key policy: {}'.format(type(policy).__name__))
        self._client.set_missing_host_key_policy(policy)

        uri = config['uri']
        try:
            self._client.connect(uri.host, uri.port or 22, uri.user,
                                 password=uri.password)
        except BadHostKeyException, e:
            raise TransportError(_BAD_KEY_ERROR.format(
                e.key.get_name(),
                format_key(e.key),
                e.expected_key.get_name(),
                format_key(e.expected_key),
                ssh_host_name(uri),
            ))
        except SSHException, e:
            if 'not found in known_hosts' in e.message:
                raise TransportError(_KNOWN_HOSTS_ERROR.format(
                    ssh_host_name(uri))
                )
            raise

        log.info('SSH connection established')
        log.debug('Verifying umask')
        um, _ = self.popen(['sh', '-c', 'umask']).communicate()
        umask = int(um.strip(), 8)
        expected_umask = int(config['reset_umask'], 8)
        if not umask == int(config['reset_umask'], 8):
            log.warning('Host has unexpected umask of {:03o} (instead of '
                        '{:03o}). Things might not work as you expect.'
                        .format(umask, expected_umask))

    @property
    def _sftp(self):
        if not self.__sftp:
            self.__sftp = self._client.open_sftp()
        return self.__sftp

    @wrap_sftp_errors
    def chdir(self, path):
        return self._sftp.chdir(path)

    @wrap_sftp_errors
    def chmod(self, path, mode):
        return self._sftp.chmod(path, mode)

    @wrap_sftp_errors
    def getcwd(self):
        return self._sftp.normalize('.')

    @wrap_sftp_errors
    def listdir(self, path):
        return self._sftp.listdir(path)

    @wrap_sftp_errors
    def lstat(self, path):
        return self._sftp.lstat(path)

    @wrap_sftp_errors
    def mkdir(self, path, mode=0777):
        return self._sftp.mkdir(path, mode)

    @wrap_sftp_errors
    def normalize(self, path):
        return self._sftp.normalize(path)

    @wrap_sftp_errors
    def readlink(self, path):
        return self._sftp.readlink(path)

    @wrap_sftp_errors
    def rename(self, oldpath, newpath):
        return self._sftp.rename(oldpath, newpath)

    @wrap_sftp_errors
    def popen(self, args, bufsize=0, extra_env={}):
        envvars = ['{}={}'.format(shlex_quote(k), shlex_quote(v))
                   for k, v in extra_env.items()]

        # get timeout from configuration
        timeout = config['ssh_command_timeout']

        if timeout:
            timeout = int(timeout)
        cmd = ' '.join(envvars + [shlex_quote(part) for part in args])
        log.debug('Executing {}'.format(cmd))
        stdin, stdout, stderr = self._client.exec_command(cmd, timeout=timeout)

        return SSHRemoteProcess(
            stdin=_ShutdownWrap(stdin, 1),
            stdout=_ShutdownWrap(stdout, 0),
            stderr=_ShutdownWrap(stderr, 0),
        )

    @wrap_sftp_errors
    def rmdir(self, path):
        return self._sftp.rmdir(path)

    @wrap_sftp_errors
    def stat(self, path):
        return self._sftp.stat(path)

    @wrap_sftp_errors
    def symlink(self, target, path):
        return self._sftp.symlink(target, path)

    @wrap_sftp_errors
    def umask(self, umask):
        _validate_umask(umask)
        raise NotImplementedError('Currently, the SSH transport does not '
                                  'support setting the umask')

    @wrap_sftp_errors
    def unlink(self, path):
        return self._sftp.unlink(path)

    @wrap_sftp_errors
    def file(self, name, mode='r', bufsize=-1):
        return self._sftp.file(name, mode, bufsize)
