from contextlib import contextmanager
import os
from stat import S_ISDIR, S_ISLNK, S_ISREG

from remand import remote, config, log
from remand.exc import (ConfigurationError, RemoteFailureError,
                        RemoteFileDoesNotExistError,
                        RemotePathIsNotADirectoryError)

from remand.operation import operation, Changed, Unchanged
import volatile

from .edit import EditableFile
from .verify import Verifier
from .upload import Uploader


def _expand_remote_dest(local_path, remote_path):
    if remote_path is None:
        if local_path is None:
            raise RuntimeError('one of local_path, remote_path is required')
        remote_path = local_path

    st = remote.lstat(remote_path)
    if st:
        # file exists, check if it is a link
        if S_ISLNK(st.st_mode):
            # normalize (dangling links will raise an exception)
            remote_path = remote.normalize(remote_path)

            # update stat
            st = remote.lstat(remote_path)

        # dir-expansion, since st is guaranteed not be a link
        if st and S_ISDIR(st.st_mode):
            if local_path is None:
                raise RemoteFailureError('Is a directory: {}'.format(
                    remote_path))

            # if it's a directory, correct path
            remote_path = remote.path.join(remote_path,
                                           remote.path.basename(local_path))

            st = remote.lstat(remote_path)
            log.debug('Expanded remote_path to {!r}'.format(remote_path))

    # ensure st is either non-existant, or a regular file
    if st and not S_ISREG(st.st_mode):
        raise RemoteFailureError(
            'Not a regular file: {!r}'.format(remote_path))
    return st, remote_path


@operation()
def chown(remote_path, uid=None, gid=None, recursive=False):
    # FIXME: Create remote_walk
    pass


@operation()
def create_dir(path, mode=0777):
    """Ensure that a directory exists at path. Parent directories are created
    if needed.

    :param path: Directory to create if it does not exist.
    :param mode: Mode for newly created parent directories.
    :param return: ``False`` if the path existed, ``True`` otherwise.
    """
    npath = remote.path.normpath(path)

    st = remote.stat(path)

    if not st:
        head, tail = remote.path.split(path)
        if tail and head:
            # create parent directories
            create_dir(head, mode)
        remote.mkdir(npath, mode)
        return Changed(msg='Created directory: {}'.format(path))

    return Unchanged('Already exists: {}'.format(path))


@contextmanager
def edit(remote_path, create=True):
    with volatile.file() as tmp:
        created = False
        if create and not remote.lstat(remote_path):
            tmp.write('')
            created = True
        else:
            tmp.write(remote.file(remote_path, 'rb').read())
        tmp.close()

        try:
            ef = EditableFile(tmp.name)
            yield ef
        except Exception:
            raise
        else:
            if created or ef.modified:
                upload_file(ef.name, remote_path).changed
                ef.changed = True
            else:
                ef.changed = False


@operation()
def remove_file(remote_path):
    """Removes a remote file, as long as it is a file or a symbolic link.

    :param remote_path: Remote file to remote.
    """
    try:
        remote.unlink(remote_path)
    except RemoteFileDoesNotExistError:
        return Unchanged(msg=u'File already gone: {}'.format(remote_path))

    return Changed(msg=u'Removed: {}'.format(remote_path))


@operation()
def remove_dir(remote_path, recursive=True):
    """Removes a remote directory.

    If the directory does not exist, does nothing.

    :param recursive: Makes ``remove_dir`` behave closer to ``rm -rf`` instead
                      of ``rmdir``.
    """
    st = remote.lstat(remote_path)

    if st is None:
        return Unchanged(msg=u'Directory already gone: {}'.format(remote_path))

    # if it is not a directory, don't touch it
    if not S_ISDIR(st.st_mode):
        raise RemotePathIsNotADirectoryError(remote_path)

    if recursive:
        for dirpath, dirnames, filenames in walk(remote_path, topdown=False):
            for fn in filenames:
                remote.unlink(remote.path.join(dirpath, fn))
            remote.rmdir(dirpath)
    else:
        remote.rmdir(dirpath)

    return Changed(msg=u'Removed directory: {}'.format(remote_path))


@operation()
def touch(remote_path):
    """Update mtime and atime of a path.

    Similar to running ``touch remote_path``.

    :param remote_path: Remote path whose times will get updated.
    :return: Since it always updates to the current time, calling this function
             will always result in a modification.
    """
    # ensure the file exists
    if not remote.lstat(remote_path):
        with remote.file(remote_path, 'w') as out:
            out.write('')

    remote.utime(remote_path, None)
    return Changed(msg=u'Touched {}'.format(remote_path))


@operation()
def upload_file(local_path, remote_path=None):
    """Uploads a local file to a remote and if does not exist or differs
    from the local version, uploads it.

    To avoid having to transfer the file one or more times if unchanged,
    different methods for verification are available. These can be configured
    using the ``fs_remote_file_verify`` configuration variable.

    :param local_path: Local file to upload. If it is a symbolic link, it will
                       be resolved first.
    :param remote_path: Remote name for the file. If ``None``, same as
                        ``local_path``. If it points to a directory, the file
                        will be uploaded to the directory. Symbolic links not
                        pointing to a directory are an error.

    :param return: ``False`` if no upload was necessary, ``True`` otherwise.
    """
    st, remote_path = _expand_remote_dest(local_path, remote_path)

    verifier = Verifier._by_short_name(config['fs_remote_file_verify'])()
    uploader = Uploader._by_short_name(config['fs_remote_file_upload'])()

    if not os.path.exists(local_path):
        raise ConfigurationError('Local file {!r} does not exist'.format(
            local_path))

    if not st or not verifier.verify_file(st, local_path, remote_path):
        uploader.upload_file(local_path, remote_path)
        if config.get_bool('fs_update_mtime'):
            lst = os.stat(local_path)
            times = (lst.st_mtime, lst.st_mtime)
            remote.utime(remote_path, times)
            log.debug('Updated atime/mtime: {}'.format(times))
        return Changed(msg='Upload {} -> {}'.format(local_path, remote_path))

    return Unchanged(msg='File up-to-date: {}'.format(remote_path))


@operation()
def upload_string(buf, remote_path):
    """Similar to :func:`~remand.lib.fs.upload_file`, but uploads a
    buffer instead of a file-like object.

    :param buf: Data to send. Can be string or unicode.
    :param remote_path: Remote name for the file. See
                        :func:`~remand.lib.fs.upload_file` for details.
    :param return: ``False`` if no upload was necessary, ``True`` otherwise.
    """
    st, remote_path = _expand_remote_dest(None, remote_path)

    verifier = Verifier._by_short_name(config['fs_remote_string_verify'])()
    uploader = Uploader._by_short_name(config['fs_remote_string_upload'])()

    if not st or not verifier.verify_buffer(st, buf, remote_path):
        uploader.upload_buffer(buf, remote_path)
        return Changed(
            msg='Upload buffer ({}) -> {}'.format(len(buf), remote_path))

    return Unchanged(msg='File up-to-date: {}'.format(remote_path))


def walk(top, topdown=True, onerror=None, followlinks=False):
    try:
        names = remote.listdir(top)
    except OSError as e:
        if onerror:
            onerror(e)
        return

    dirs, files = [], []
    for name in names:
        fn = remote.path.join(top, name)
        st = remote.lstat(fn)

        if S_ISDIR(st.st_mode):
            dirs.append(name)
        else:
            files.append(name)

    if topdown:
        yield top, dirs, files

    for name in dirs:
        fn = remote.path.join(top, name)
        st = remote.lstat(fn)

        if followlinks or not S_ISLNK(st.st_mode):
            for rv in walk(fn, topdown, onerror, followlinks):
                yield rv

    if not topdown:
        yield top, dirs, files
