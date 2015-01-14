from contextlib import contextmanager
import shlex
from six.moves import shlex_quote

from remand import remote, log, config
from remand.exc import RemoteFailureError
from remand.remotes.ssh import SSHRemote


def _cmd_to_args(cmd):
    if isinstance(cmd, list):
        return cmd

    return shlex.split(cmd)


def run(cmd, input=None, extra_env={}):
    args = _cmd_to_args(cmd)
    log.debug('run: {}'.format(args))

    proc = remote.popen(args, extra_env=extra_env)
    stdout, stderr = proc.communicate(input)

    if not proc.returncode == 0:
        log.debug('stderr: {}'.format(stderr))
        raise RemoteFailureError('Remote command {} exited with exit status {}'
                                 .format(args, proc.returncode))

    return stdout, stderr


@contextmanager
def sudo(user=None, password=None):
    if not isinstance(remote._get_current_object(), SSHRemote):
        raise NotImplementedError('sudo is only supported for SSH remotes.')

    sudo_args = ['sudo', '-E', '-H']

    if user:
        sudo_args.append('-u', user)
    if password:
        raise NotImplementedError('Currently, sudo with password is not '
                                  'supported.')

    def sudo_popen(args, bufsize=0, extra_env={}):
        # -E preserve environment variables passed
        # -H set the $HOME environment variable (usually default)
        # -S (unused): read password from stdin

        sudo_args.extend(args)
        return orig_popen(sudo_args, bufsize, extra_env)

    # monkey patch remote.sudo
    orig_popen = remote.popen
    remote.popen = sudo_popen

    sftp_cmd = ' '.join([shlex_quote(part) for part in sudo_args]
                        + [config['sftp_location']])

    # override sftp subsystem
    config['sftp_command'] = sftp_cmd

    yield
    remote.popen = orig_popen
