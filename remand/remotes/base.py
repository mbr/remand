from contextlib import contextmanager
import posixpath

from .. import util, config


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
        collect_stdout = util.CollectThread(self.stdout)
        collect_stderr = util.CollectThread(self.stderr)

        bufsize = int(config['buffer_size'])
        if input is not None:
            util.write_all(self.stdin, input)
        self.stdin.close()

        # wait for stdout/stderr to finish
        collect_stdout.join()
        collect_stderr.join()

        self.wait()

        return (collect_stdout.get_result(), collect_stderr.get_result())

    def kill(self):
        """Kill the remote process.

        Tries to kill the remote process as fast as possible.
        """
        raise NotImplementedError


class Remote(object):
    """Interface for transports to remote server.

    All instance-methods will throw :class:`~remand.exc.RemoteFailureError` if
    the operation is not successful (in addition to the usual
    :class:`~remand.exc.TransportError`).
    """

    #: the path module to be used on the remote
    path = posixpath

    def getcwd(self):
        """Returns the current working directory.

        :return: The current working directory as a string."""
        return self.normalize('.')

    def chdir(self, path):
        """Change the current working directory to ``path``.

        :param path: The new working directory as a string.
        """
        raise NotImplementedError

    def chmod(self, path, mode):
        """Change ownership of path.

        :param path: Path to change ownership of.
        :param mode: New mode (as an integer, e.g. ``0755``).
        """
        raise NotImplementedError

    def chown(self, path, uid=-1, gid=-1):
        """Change ownership of a file.

        :param path: Path to change ownership of.
        :param uid: User id to change to (numeric).
        :param gid: Group id to change to (numeric).
        """
        raise NotImplementedError

    def file(self, name, mode='r', bufsize=-1):
        """Open a file on the remote side.

        This function mimicks the Python :func:`file` interface, except that
        the parameter ``buffering`` is called ``bufsize`` instead.

        When dealing with remote files, :ref:`umask` should be taken into
        account.

        :return: A file-like object
        """
        raise NotImplementedError

    def listdir(self, path):
        """List directory contents.

        :param path: Directory to list.
        :return: List of strings containing all directory entries.
        """
        raise NotImplementedError

    def lstat(self, path):
        """Stat without following symbolic links.

        See :func:`~remand.remotes.Remand.stat`.
        """
        raise NotImplementedError

    def mkdir(self, path, mode=None):
        """Create directory.

        :param path: Path to create.
        :param mode: The final mode for the new directory. umask will be
        applied, see :ref:`umask`.
        """
        raise NotImplementedError

    def normalize(self, path):
        """Normalize a path.

        :param path: Path to normalize.
        :return: Resulting path, with all links followed and relative dirs
                 resolved.
        """
        raise NotImplementedError

    def open(self, *args, **kwargs):
        """Alias for `.file()`"""
        return self.file(*args, **kwargs)

    def popen(self, args, cwd=None, extra_env={}):
        """Open a process on the remote side.

        :param args: The command's args (including argv0)
        :param cwd: If not ``None``, change to this directory before executing.
        :param extra_env: Dictionary of additional environment variables to
                          set before executing.
        :return: A :class:`~remand.remotes.RemoteProcess` instance.
        """
        raise NotImplementedError

    def readlink(self, path):
        """Read a symbolic link.

        :param path: Link to read.
        :return: A string with the link's target.
        """
        raise NotImplementedError

    def rename(self, oldpath, newpath):
        """Rename a file.

        Existing paths will be silently overwritten.

        :param oldpath: Path to be renamed.
        :param newpath: New name for the path.
        """
        raise NotImplementedError

    def rmdir(self, path):
        """Remove a directory.

        :param path: Directory to remove.
        """
        raise NotImplementedError

    def stat(self, path):
        """Stat a file.

        :param path: Path to stat
        :return: A stat result that supports attribute access to the following
                 fields: ``st_size``, ``st_uid``, ``st_gid``, ``st_mode``,
                 ``st_atime``, ``st_mtime`` with the same meanings as those
                 of :func:`os.stat`.

                 If the path does not exist, returns ``None`` without throwing
                 an exception.
        """
        raise NotImplementedError

    def symlink(self, target, path):
        """Create a symbolic link.

        :param target: Where the link will point.
        :param path: Path for the link.
        """
        raise NotImplementedError

    def tcp_connect(self, addr):
        """Open a TCP connection from the remote.

        This method must be callable from threads other than the remote's own.

        :param addr: Destination address to connect to.
        :return: A socket-like object.
        """
        raise NotImplementedError

    def umask(self, umask):
        """Set the current umask and return the previous one.

        :param umask: New umask as an integer.
        :return: Previous umask.
        """
        raise NotImplementedError

    def unix_connect(self, addr):
        """Open a unix domain socket connection from the remote.

        This method must be callable from threads other than the remote's own.

        :param addr: Destination address to connect to.
        :return: A socket-like object.
        """
        raise NotImplementedError

    def unlink(self, path):
        """Remove a file.

        :param path: File to remove.
        """
        raise NotImplementedError

    def utime(self, path, times):
        """Set atime/mtime of path.

        :param times: A tuple of ``(atime, mtime)``.
        """
        raise NotImplementedError

    @contextmanager
    def umasked(self, context_umask):
        """Temporary umask context manager.

        :param context_umask: Umask to set within context.
        """
        old_umask = self.umask(context_umask)
        yield
        self.umask(old_umask)
