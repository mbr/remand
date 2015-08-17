from binascii import hexlify
from contextlib import contextmanager
from os import urandom
import shlex
from six.moves import shlex_quote
from time import time

from remand import remote, log, config
from remand.exc import RemoteFailureError
from remand.remotes.ssh import SSHRemote


def _cmd_to_args(cmd):
    if isinstance(cmd, list):
        return cmd

    return shlex.split(cmd)


def run(cmd, input=None, extra_env={}, status_ok=(0, )):
    args = _cmd_to_args(cmd)

    proc = remote.popen(args, extra_env=extra_env)
    stdout, stderr = proc.communicate(input)

    if not proc.returncode in status_ok:
        log.debug('stderr: {}'.format(stderr))
        raise RemoteFailureError('Remote command {} exited with exit status {}'
                                 .format(args, proc.returncode))

    return stdout, stderr, proc.returncode


@contextmanager
def sudo(user=None, password=None, timestamp_timeout=2 * 60):
    if not isinstance(remote._get_current_object(), SSHRemote):
        raise NotImplementedError('sudo is only supported for SSH remotes.')

    # --preserve-env, --set-home and --non-interactive
    # long options are not supported on older versions of sudo
    sudo_args = ['sudo', '-E', '-H', '-n']

    if user:
        sudo_args.append('--user={}'.format(user))

    prev_timestamp = [0]

    def sudo_popen(args, bufsize=0, extra_env={}):
        # -E preserve environment variables passed
        # -H set the $HOME environment variable (usually default)
        # -S (unused): read password from stdin

        if password:
            cur = time()
            if cur - prev_timestamp[0] > timestamp_timeout:
                # customize our prompt, to prevent accidentally entering the
                # password. note that this is visible on the sudo invocation
                # and therefore not a security measure
                prompt_cookie = hexlify(urandom(40))
                log.debug('Prompt cookie for sudo refresh: {}'.format(
                    prompt_cookie))

                # we need to refresh the sudo timestamp
                refresh_args = [
                    'sudo',
                    '-k',  # --reset-timestamp
                    '-v',  # --validate
                    '-S',  # --stdin
                    '--prompt={}'.format(prompt_cookie)
                ]

                proc = orig_popen(refresh_args)
                log.debug('Checking prompt cookie...')
                if not proc.stderr.read(len(prompt_cookie)) == prompt_cookie:
                    raise RemoteFailureError('Unexpected output from sudo, '
                                             'bailing out.')

                # shove in the password
                stdout, stderr = proc.communicate(password + '\n')

                if proc.returncode != 0:
                    raise RemoteFailureError(
                        'Could not refresh sudo timestmap (exit status: {}).'
                        'The most common occurence for this is an incorrect '
                        'password.'.format(proc.returncode))

                # from this point on, sudo should work without a password
                # until the timestamp expires
                prev_timestamp[0] = cur

                # FIXME: handle SFTP

        pargs = sudo_args[:]

        pargs.append('--')
        pargs.extend(args)
        return orig_popen(pargs, bufsize, extra_env)

    # monkey patch remote.sudo
    orig_popen = remote.popen
    remote.popen = sudo_popen

    sftp_cmd = ' '.join([shlex_quote(part)
                         for part in sudo_args] + [config['sftp_location']])

    # override sftp subsystem
    config['sftp_command'] = sftp_cmd

    yield
    remote.popen = orig_popen

    # FIXME: remove sudo credentials
