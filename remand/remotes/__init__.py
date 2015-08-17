import os
import shlex

from six.moves import shlex_quote

from ..exc import ConfigurationError


def quote_args(args):
    return ' '.join(shlex_quote(arg) for arg in args)


class _RunDispatchMixin(object):
    def _run_args(self, cmd_args, *args, **kwargs):
        return self._run_cmd(shlex_quote(cmd_args), *args, **kwargs)

    def _run_cmd(self, cmd, *args, **kwargs):
        return self._run_args(shlex.split(cmd), *args, **kwargs)

    def run(self, cmd, *args, **kwargs):
        if isinstance(cmd, list):
            return self._run_args(cmd, *args, **kwargs)
        return self._run_cmd(cmd, *args, **kwargs)


# FIXME:
class Project(object):
    def __init__(self, basedir):
        self.basedir = basedir

    def get_resource(self, parts):
        return os.path.join(self.basedir, *parts)


def _validate_umask(umask):
    if not isinstance(umask, int):
        raise ConfigurationError('Not an integer umask: {}'.format(umask))
    if umask > 0777:
        raise ConfigurationError('Invalid umask value: {}'.format(umask))
