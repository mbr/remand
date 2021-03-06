from binascii import hexlify
from functools import wraps, partial
from threading import Thread
import os
import socket
import time

import click
from future.utils import raise_from
from paramiko.client import (SSHClient, AutoAddPolicy, RejectPolicy,
                             MissingHostKeyPolicy)
from paramiko.sftp_client import SFTPClient
from paramiko.ssh_exception import (SSHException, BadHostKeyException,
                                    NoValidConnectionsError)
from six.moves import shlex_quote

from .. import config, log, util
from .base import Remote, RemoteProcess
from ..exc import (TransportError, RemoteFailureError,
                   RemoteFileDoesNotExistError, ConfigurationError)

_KNOWN_HOSTS_ERROR = (
    "The host '{}' was not found in your known_hosts file. "
    "Remand is refusing to connect to unknown hosts.\n\n"
    "If you have an older version of Paramiko installed, this may be because "
    "of a key-type mismatch.\n\n"
    "See https://github.com/paramiko/paramiko/pull/473 for more information.")

_BAD_KEY_ERROR = (
    # for extra drama, we copy the openssh error message:
    "The remote host's key does not match the key in your known_hosts file.\n"
    "IT IS POSSIBLE THAT SOMEONE IS DOING SOMETHING NASTY!\n\n"
    "Remote host key: {} {}\n"
    "known_hosts key: {} {}\n\n"
    "The host key for '{}' has changed and checking is enabled.")

_PRIVATE_KEY_ENCRYPTED = (
    "A suitable private key for authentication was found, but it is password "
    "protected. Please use ssh-agent to authenticate with password protected "
    "keys. If you are seeing this message despite having ssh-agent running, "
    "either the key is missing or something went wrong with authenticating "
    "with it")


class WarnAutoAddPolicy(AutoAddPolicy):
    def missing_host_key(self, client, hostname, key):
        log.warning('Missing hostkey for {} ignored (fingerprint is {}).'
                    .format(hostname, format_key(key)))
        return super(WarnAutoAddPolicy, self).missing_host_key(
            client, hostname, key)


class AskToAddPolicy(MissingHostKeyPolicy):
    _UNKNOWN_WARNING = ("The authenticity of host '{}' can't be established.\n"
                        "{} key fingerprint is {}.")
    _USER_PROMPT = "Are you sure you want to continue connecting?"

    def missing_host_key(self, client, hostname, key):
        click.echo(
            self._UNKNOWN_WARNING.format(
                hostname,
                key.get_name(),
                format_key(key), ))
        if not click.confirm(self._USER_PROMPT):
            raise TransportError('User declined to connect to unknown host')


class AskToSavePolicy(AskToAddPolicy):
    _USER_PROMPT = (
        "Are you sure you want to save to known_hosts and continue?")

    def missing_host_key(self, client, hostname, key):
        super(AskToSavePolicy, self).missing_host_key(client, hostname, key)

        # add, this does not save it though
        client._host_keys.add(hostname, key.get_name(), key)

        if client._host_keys_filename is not None:
            client.save_host_keys(client._host_keys_filename)
            log.info('Added {} host key for {}: {}'.format(
                key.get_name(), hostname, format_key(key)))
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
            raise TransportError(
                'SSH ({}): {}'.format(type(e).__name__, e.message))

    return _


def wrap_sftp_errors(f):
    @wraps(f)
    def _(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except IOError, e:
            fargs = ', '.join(
                map(repr, args[1:]) +
                ['{}={!r}'.format(*v) for v in kwargs.items()])
            if e.errno == 2:
                raise RemoteFileDoesNotExistError(str(e))
            raise RemoteFailureError(
                'SFTP Failed {}({}): {}'.format(f.__name__, fargs, str(e)))

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

    _sftp_instance = None

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
        timeout = int(config['ssh_connect_timeout'])
        port = uri.port or 22
        attempt = 0
        max_attempts = int(config['ssh_connect_retries'])
        delay = int(config['ssh_connect_retry_delay'])

        while True:
            if attempt == 0:
                log.debug(
                    'First connection attempt to {}:{}'.format(uri.host, port))
            try:
                self._client.connect(
                    uri.host,
                    port,
                    uri.user,
                    password=uri.password,
                    key_filename=config['ssh_private_key'] or None,
                    timeout=timeout,
                    look_for_keys=True,
                    allow_agent=True)
                break
            except BadHostKeyException, e:
                raise TransportError(
                    _BAD_KEY_ERROR.format(
                        e.key.get_name(),
                        format_key(e.key),
                        e.expected_key.get_name(),
                        format_key(e.expected_key),
                        ssh_host_name(uri), ))
            except (socket.timeout, NoValidConnectionsError) as e:
                attempt += 1

                msg = ('Connection to {}:{} failed {} out of {} times'.format(
                    uri.host, port, attempt, max_attempts))
                log.warning(msg)

                if attempt < max_attempts:
                    log.info('Retrying to connect in {} seconds'.format(delay))
                    time.sleep(delay)
                    continue

                raise TransportError(
                    'Could not connect to {}:{}'.format(uri.host, port))
            except SSHException, e:
                if 'not found in known_hosts' in e.message:
                    raise TransportError(
                        _KNOWN_HOSTS_ERROR.format(ssh_host_name(uri)))
                if 'Private key file is encrypted' in e.message:
                    raise TransportError(_PRIVATE_KEY_ENCRYPTED)
                raise

        log.debug('SSH connection established')

        # verify umask
        log.debug('Verifying umask')
        p_umask = self.popen(['sh', '-c', 'umask'])
        um, _ = p_umask.communicate()
        assert p_umask.returncode == 0

        umask = int(um.strip(), 8)
        expected_umask = int(config['reset_umask'], 8)
        if not umask == int(config['reset_umask'], 8):
            log.warning('Host has unexpected umask of {:03o} (instead of '
                        '{:03o}). Things might not work as you expect.'.format(
                            umask, expected_umask))

        # verify time
        max_diff = config['max_time_diff']

        if max_diff is not None:
            local_timestamp = int(time.time())
            p_ts = self.popen(['date', '+%s'])
            try:
                ts, _ = p_ts.communicate()
            except IOError as e:
                log.warning('Could not verify remote time. '
                            'Is the date binary missing?')
            timestamp = int(ts)
            time_diff = timestamp - local_timestamp
            log.debug('Local time: {} Remote time: {} Diff: {}'.format(
                local_timestamp, timestamp, time_diff))
            if time_diff > max_diff:
                log.warning('Remote time differs by {} seconds (limit: {})'
                            .format(time_diff, max_diff))

    @property
    def _sftp(self):
        if self._sftp_instance:
            # check if the command changed
            if config['sftp_command'] != self._sftp_invocation:
                self._sftp_instance.close()

                self._sftp_invocation = None
                self._sftp_instance = None
                log.debug('SFTP command changed, reinitializing SFTP')

        if not self._sftp_instance:
            t = self._client._transport
            chan = t.open_session()
            if chan is None:
                raise TransportError('Could not open channel for SFTP')

            if config['sftp_command'] is None:
                log.debug('SFTP using Subsystem sftp')
                chan.invoke_subsystem('sftp')
            else:
                log.debug('SFTP using {}'.format(config['sftp_command']))
                chan.exec_command(config['sftp_command'])
            self._sftp_invocation = config['sftp_command']
            self._sftp_instance = SFTPClient(chan)

        return self._sftp_instance

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
        try:
            return self._sftp.lstat(path)
        except IOError, e:
            if e.errno == 2:
                return None
            raise

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
    def popen(self, args, cwd=None, extra_env={}):
        envvars = [
            '{}={}'.format(shlex_quote(k), shlex_quote(v))
            for k, v in extra_env.items()
        ]
        chdir = ''

        if cwd is not None:
            chdir = 'cd {} &&'.format(shlex_quote(cwd))

        # get timeout from configuration
        timeout = config['ssh_command_timeout']

        if timeout:
            timeout = int(timeout)
        cmd = ' '.join([chdir] + envvars +
                       [shlex_quote(part) for part in args])
        log.debug('Executing {}'.format(cmd))
        stdin, stdout, stderr = self._client.exec_command(cmd, timeout=timeout)

        return SSHRemoteProcess(
            stdin=_ShutdownWrap(stdin, 1),
            stdout=_ShutdownWrap(stdout, 0),
            stderr=_ShutdownWrap(stderr, 0), )

    @wrap_sftp_errors
    def rmdir(self, path):
        return self._sftp.rmdir(path)

    @wrap_sftp_errors
    def stat(self, path):
        try:
            return self._sftp.stat(path)
        except IOError, e:
            if e.errno == 2:
                return None
            raise

    @wrap_sftp_errors
    def symlink(self, target, path):
        return self._sftp.symlink(target, path)

    def tcp_connect(self, addr):
        # cannot log here, must be callable by other threads

        t = self._client._transport
        chan = t.open_channel(
            'direct-tcpip',
            dest_addr=addr,
            src_addr=('127.0.0.1', 0)  # not needed
        )

        if not chan:
            raise IOError('Could not open TCP tunnel to {}:{}'.format(*addr))

        return chan

    @wrap_sftp_errors
    def umask(self, umask):
        try:
            util.validate_umask(umask)
        except ValueError as e:
            raise_from(ConfigurationError(str(e)), e)
        raise NotImplementedError('Currently, the SSH transport does not '
                                  'support setting the umask')

    def unix_connect(self, addr):
        # FIXME: this could work directly on OpenSSH 6.7+
        if not config['cmd_nc-openbsd']:
            # FIXME: if the command is set, but not present on the remote
            #        side, this will cause a confusing error message
            #        (server unexpectedly closed the connection)
            #
            #        maybe check once beforehand for the present of the tool?
            #
            # FIXME: this issue will also occur if the wrong netcat is
            # installed (`netcat-traditional` vs `netcat-openbsd`)
            raise ValueError('cmd.nc-openbsd is required for unix socket '
                             'connections via SSH')

        p = self.popen([config['cmd_nc-openbsd'], '-U', addr])
        return p._channel

    @wrap_sftp_errors
    def unlink(self, path):
        return self._sftp.unlink(path)

    @wrap_sftp_errors
    def utime(self, path, times):
        return self._sftp.utime(path, times)

    @wrap_sftp_errors
    def file(self, name, mode='r'):
        fp = self._sftp.file(name, mode, int(config['buffer_size']))
        fp.set_pipelined(config.get_bool('sftp_pipelined'))
        return fp
