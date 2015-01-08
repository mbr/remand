import os
import shlex

from six.moves import shlex_quote


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


class Remote(object):
    def run(self, cmd):
        raise NotImplementedError

    def getcwd(self):
        return self.normalize('.')

    def chdir(self, path):
        raise NotImplementedError

    def chmod(self, path, mode):
        raise NotImplementedError

    def chown(self, uid=-1, gid=-1):
        raise NotImplementedError

    def listdir(self, path):
        raise NotImplementedError

    def mkdir(self, path, mode):
        raise NotImplementedError

    def makedirs(self, path, mode):
        raise NotImplementedError

    def normalize(self, path):
        raise NotImplementedError

    def file(self, name, mode='r', buffering=-1):
        raise NotImplementedError

    def readlink(self, path):
        raise NotImplementedError

    def rename(self, path):
        raise NotImplementedError

    def rmdir(self, path):
        raise NotImplementedError

    def stat(self, path):
        raise NotImplementedError

    def symlink(self, path):
        raise NotImplementedError

    def unlink(self, path):
        raise NotImplementedError

    def get(self, remote_path, local_path):
        raise NotImplementedError

    def put(self, remote_path, local_path):
        raise NotImplementedError
