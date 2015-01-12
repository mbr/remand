import shlex

from remand import remote, log
from remand.exc import RemoteFailureError


def _cmd_to_args(cmd):
    if isinstance(cmd, list):
        return cmd

    return shlex.split(cmd)


def run(cmd, input=None):
    args = _cmd_to_args(cmd)
    log.debug('run: {}'.format(args))

    proc = remote.popen(args)
    stdout, stderr = proc.communicate(input)

    if not proc.returncode == 0:
        log.debug('stderr: {}'.format(stderr))
        raise RemoteFailureError('Remote command exited with exit status {}'
                                 .format(proc.returncode))

    return stdout, stderr
