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


class RemoteProcess(object):
    """A remote process represents a process running on a remote instance.

    It somewhat mimicks the interface of :class:`subprocess.Popen`, but due
    to its more abstract nature cannot support all of its features.

    This class is not meant to be instantiated directly, use
    :class:`remand.remotes.Remote` create an instance.
    """
    #: The remote process' stdout
    stdout = None

    #: The remote process' stderr
    stderr = None

    #: The remote process' stdin
    stdin = None

    #: The remote process' exit code. Will be ``None`` if the process is still
    #:  running.
    returncode = None

    def poll(self):
        """Check if the process is still running.

        :return: A boolean indicating whether or not the process is still
        running."""
        return self.returncode is None

    def wait(self):
        """Wait for the process to complete.

        :note: This should rarely be used, as it will deadlock if the process
        fills up the stdout/stderr buffer. Use communicate instead of this.
        """
        raise NotImplementedError

    def communicate(self, input=None):
        """Interact with the remote process.

        Will retrieve data from stdout and stderr into memory buffers, then
        return those, optionally passing in ``input``.

        :param input: Data to send to stdin.
        :return: A tuple of ``(stdoutdata, stderrdata)``.
        """
        raise NotImplementedError

    def kill(self):
        """Kill the remote process.

        Tries to kill the remote process as fast as possible.
        """
        raise NotImplementedError


class Remote(object):
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

    def lstat(self, path):
        raise NotImplementedError

    def mkdir(self, path, mode):
        raise NotImplementedError

    def normalize(self, path):
        raise NotImplementedError

    def popen(self, args, bufsize=0, extra_env=None):
        """Open a process on the remote side.

        :param args: The command's args (including argv0)
        :param bufsize: Buffer size
        :param extra_env: Dictionary of additional environment variables to
                          set before executing.
        :return: A :class:`~remand.remotes.RemoteProcess` instance.
        """
        raise NotImplementedError

    def file(self, name, mode='r', bufsize=-1):
        raise NotImplementedError

    def readlink(self, path):
        raise NotImplementedError

    def rename(self, oldpath, newpath):
        raise NotImplementedError

    def rmdir(self, path):
        raise NotImplementedError

    def stat(self, path):
        raise NotImplementedError

    def symlink(self, path):
        raise NotImplementedError

    def unlink(self, path):
        raise NotImplementedError
