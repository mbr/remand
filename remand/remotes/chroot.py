import os
import subprocess

from .. import log, util, config
from .base import Remote, RemoteProcess


def _is_subpath(path, start):
    """Checks if a `path` is a subpath of `start`. Will follow symbolic links
    to check if they are pointing outside"""

    # normalize both paths
    start = os.path.abspath(os.path.realpath(start))
    path = os.path.abspath(os.path.realpath(path))

    return (path + os.sep).startswith(start + os.sep)


class ChrootViolation(Exception):
    pass


class ChrootRemote(Remote):
    """chroot-based remote

    Will executate all commands in a chroot (paths are taken relative to the
    chroot as well, even if they are absolute).
    """

    def __init__(self):
        # verify umask, same as local remote
        umask = int(config['reset_umask'], 8)
        log.debug('Setting umask to {:o}'.format(umask))
        os.umask(umask)

        uri = config['uri']

        # ensure chroot is not mistakenly misused
        assert not uri.host
        assert not uri.port
        assert uri.user == 'root'

        # ensure that self root has the form `/foo/bar` with no trailing slash
        self.root = os.path.abspath(uri.path)
        assert not self.root.endswith(os.sep)

        self._cwd = '/'

    def _lpath(self, rpath):
        """Convert a path from inside the chroot into one mapped onto the local
        filesystem.

        Will raise :class:`.ChrootViolation` is `path` is outside the
        chroot."""

        # store path in case we need it later for the exception message
        path = rpath

        if not os.path.isabs(path):
            # self._cwd is always absolute
            path = os.path.join(self._cwd, path)

        # path is guaranteed to be absolute now, we can add it to lpath
        lpath = self.root + path

        # normalize the lpath
        lpath = self.path.abspath(lpath)

        # security check: ensure we're not accidentally leaving the chroot
        if not _is_subpath(lpath, self.root):
            raise ChrootViolation(
                "Path {} violates chroot of {} [cwd: {}]".format(
                    path, self.root, self._cwd))

        return lpath

    def _rpath(self, lpath):
        """Convert a path from local filesystem to chroot path. Will raise
        :class:`.ChrootViolation` if `lpath` is outside the chroot."""
        if not _is_subpath(lpath, self.root):
            raise ChrootViolation("Not in {} chroot: {}".format(self.root,
                                                                lpath))
        rpath = self.path.abspath()

    def getcwd(self):
        return self._cwd

    def chdir(self, path):
        self._cwd = os.path.join(self._cwd, path)
        assert os.path.isabs(self._cwd)
        return self._cwd

    def chmod(self, path, mode):
        return os.chmod(self._lpath(path), mode)

    def chown(self, path, uid=-1, gid=-1):
        return os.chown(self._lpath(path), uid, gid)

    def file(self, name, mode='r'):
        return open(self._lpath(name), mode)

    def listdir(self, path):
        return os.listdir(self._lpath(path))

    def lstat(self, path):
        lpath = self._lpath(path)
        if not os.path.exists(lpath):
            return None

        return os.lstat(lpath)

    def mkdir(self, path, mode=None):
        return os.mkdir(self._lpath(path), mode)

    def normalize(self, path):
        lpath = self.lpath(path)

        # strip common prefix, add leading '/'
        return os.sep + lpath[len(self.root)]

    def popen(self, args, cwd=None, extra_env={}):
        env = {}
        env.update(os.environ)
        env.update(extra_env)

        proc = subprocess.Popen(args,
                                cwd=cwd or self.getcwd(),
                                env=env,
                                stdin=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                stdout=subprocess.PIPE)

        # FIXME: copied from LocalRemote; both need replacement
        orig_communicate = proc.communicate

        # decorate communicate to accept read instances
        def _communicate(input):
            if input and hasattr(input, 'read'):
                input = input.read()
            return orig_communicate(input)

        proc.communicate = _communicate

        return proc

    def readlink(self, path):
        return self._rpath(os.readlink(self._lpath(path)))

    def rename(self, oldpath, newpath):
        loldpath = self._lpath(oldpath)
        lnewpath = self._lpath(newpath)

        return os.rename(loldpath, lnewpath)

    def rmdir(self, path):
        return os.rmdir(self._lpath(path))

    def stat(self, path):
        lpath = self._lpath(path)

        if not os.path.exists(lpath):
            return None

        return os.stat(lpath)

    def symlink(self, target, path):
        return os.symlink(target, self._lpath(path))

    def tcp_connect(self, addr):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(addr)
        return s

    def umask(self, umask):
        return os.umask(umask)

    def unlink(self, path):
        return os.unlink(self._lpath(path))

    def utime(self, path, times):
        return os.utime(self._lpath(path), times)
