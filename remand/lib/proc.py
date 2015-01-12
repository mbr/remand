import shlex

from remand import remote, log
from remand.exc import RemoteFailureError


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
        raise RemoteFailureError('Remote command exited with exit status {}'
                                 .format(proc.returncode))

    return stdout, stderr
