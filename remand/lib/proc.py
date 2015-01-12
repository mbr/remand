from contextlib import contextmanager
import shlex

from remand import remote, log, state
from remand.exc import RemoteFailureError


def _popen(*args, **kwargs):
    if state['sudo']:
        return state['sudo'][-1].popen(*args, **kwargs)
    return remote.popen(*args, **kwargs)


def _cmd_to_args(cmd):
    if isinstance(cmd, list):
        return cmd

    return shlex.split(cmd)


def run(cmd, input=None, extra_env={}):
    args = _cmd_to_args(cmd)
    log.debug('run: {}'.format(args))

    proc = _popen(args, extra_env=extra_env)
    stdout, stderr = proc.communicate(input)

    if not proc.returncode == 0:
        log.debug('stderr: {}'.format(stderr))
        raise RemoteFailureError('Remote command exited with exit status {}'
                                 .format(proc.returncode))

    return stdout, stderr


class _SudoContext(object):
    def __init__(self, user, password):
        self.user = user
        self.password = password

        if self.password:
            raise NotImplementedError('At this time, sudo with password is '
                                      'not implemented.')

    def popen(self, args, bufsize=0, extra_env={}):
        # -E preserve environment variables passed
        # -H set the $HOME environment variable (usually default)
        # -S (unused): read password from stdin
        sudo_args = ['sudo', '-E', '-H']

        if self.user:
            sudo_args.append('-u', self.user)
        sudo_args.extend(args)

        return remote.popen(sudo_args, bufsize, extra_env)

    def __repr__(self):
        return 'sudo({}, {})'.format(
            self.user, '***' if self.password is not None else None)


@contextmanager
def sudo(user=None, password=None):
    if not hasattr(state, 'sudo'):
        state['sudo'] = []

    state['sudo'].append(_SudoContext(user, password))
    log.debug('Sudo stack grown to {}'.format(state['sudo']))

    yield

    state['sudo'].pop()
    log.debug('Sudo stack pop(): {}'.format(state['sudo']))
