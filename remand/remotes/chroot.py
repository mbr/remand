import os
from multiprocessing import Process, Queue
import queue

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


class ChrootProcess(RemoteProcess):
    stdout = None
    stderr = None
    stdin = None

    _returncode = None

    @property
    def returncode(self):
        if self._returncode is not None:
            return self._returncode

        try:
            rc = self._result_channel.get_nowait()
        except queue.Empty:
            return None

        # exceptions
        if isinstance(rc, Exception):
            log.error('Chrooted process failed: {}'.format(rc))
            self._returncode = -1
            return -1

        self._returncode = rc
        return rc

    def __init__(self, remote, args, cwd=None, extra_env={}):
        self._remote = remote
        self._ctrl_proc = Process(target=self.run)
        self._ctrl_proc.daemon = True
        self._args = args
        self._cwd = cwd
        self._extra_env = extra_env

        # create the necessary pipes for the process
        (stdout_r, self._stdout_w) = os.pipe()
        (stderr_r, self._stderr_w) = os.pipe()
        (self._stdin_r, stdin_w) = os.pipe()

        self.stdout = os.fdopen(stdout_r, 'rb')
        self.stderr = os.fdopen(stderr_r, 'rb')
        self.stdin = os.fdopen(stdin_w, 'wb')

        # create channel for return info
        self._result_channel = Queue()

        # immediately start
        self._ctrl_proc.start()

        # close our fd ends
        os.close(self._stdout_w)
        os.close(self._stderr_w)
        os.close(self._stdin_r)

    def run(self):
        # NOTE: `run` is executed in a seperate process

        try:
            os.chroot(self._remote.root)

            # create environment
            env = {}
            env.update(os.environ)
            env.update(self.extra_env)

            # open the subprocess
            proc = subprocess.Popen(args,
                                    cwd=self.cwd or self._remote.cwd,
                                    env=env,
                                    stdin=self._stdin_r,
                                    stderr=self._stderr_w,
                                    stdout=self._stdout_w)
            proc.join()
        except Exception as e:
            self._result_channel.put(e)
        else:
            self._result_channel.put(proc.returncode)
        finally:
            self._close_fds()

    def poll(self):
        return _ctrl_proc.is_alive()

    def wait(self):
        self._ctrl_proc.join()

    def kill(self):
        self._ctrl_proc.terminate()
        self._close_fds()

    def _close_fds(self):
        os.close(self._stdin_r)
        os.close(self._stderr_w)
        os.close(self._stdout_w)


class ChrootRemote(Remote):
    """chroot-based remote

    Will executate all commands in a chroot (paths are taken relative to the
    chroot as well, even if they are absolute).
    """

    def __init__(self):
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
        return os.mkdir(self._lpath(path, mode))

    def normalize(self, path):
        lpath = self.lpath(path)

        # strip common prefix, add leading '/'
        return os.sep + lpath[len(self.root)]

    def popen(self, args, cwd=None, extra_env={}):
        return ChrootProcess(self, args, cwd, extra_env)

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
