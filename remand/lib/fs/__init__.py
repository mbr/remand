from binascii import hexlify
from contextlib import contextmanager
import os
from stat import S_ISDIR, S_ISLNK, S_ISREG

from remand import remote, config, log
from remand.lib import proc
from remand.exc import (
    ConfigurationError, RemoteFailureError, RemoteFileDoesNotExistError,
    RemotePathIsNotADirectoryError, RemotePathIsNotALinkError)

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
                raise RemoteFailureError(
                    'Is a directory: {}'.format(remote_path))

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
    new_owner = ':'

    # no-op
    if uid is None and gid is None:
        return

    if uid is not None:
        new_owner = str(uid) + new_owner
    if gid is not None:
        new_owner += str(gid)

    cmd = [config['cmd_chown']]

    if recursive:
        cmd.append('-R')

    cmd.append('-c')  # FIXME: on BSDs, we need -v here?

    cmd.append(new_owner)
    cmd.append(remote_path)

    stdout, _, _ = proc.run(cmd)

    if stdout.strip():
        return Changed(msg='Changed ownership of {} to {}'.format(
            remote_path, new_owner))

    return Unchanged(msg='Ownership of {} already {}'.format(
        remote_path, new_owner))


@operation()
def chmod(remote_path, mode, recursive=False, executable=False):
    # FIXME: instead of executable, add parsing of rwxX-style modes
    # FIXME: add speedup by using local chmod
    xmode = mode if not executable else mode | 0o111

    st = remote.lstat(remote_path)

    if mode > 0o777:
        raise ValueError('Modes above 0o777 are not supported')

    changed = False
    actual_mode = st.st_mode & 0o777

    # if the target is a directory or already has at least one executable bit,
    # we apply the executable mode (see chmod manpage for details)
    correct_mode = (xmode
                    if S_ISDIR(st.st_mode) or actual_mode & 0o111 else mode)

    if actual_mode != correct_mode:
        remote.chmod(remote_path, correct_mode)
        changed = True

    if recursive and S_ISDIR(st.st_mode):
        for rfn in remote.listdir(remote_path):
            changed |= chmod(
                remote.path.join(remote_path, rfn), mode, True,
                executable).changed

    if changed:
        return Changed(msg='Changed mode of {} to {:o}'.format(
            remote_path, mode))

    return Unchanged(msg='Mode of {} already {:o}'.format(remote_path, mode))


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


@contextmanager
def remote_tmpdir(delete=True, randbytes=16, mode=0o700):
    # FIXME: audit this for security issues

    if config['cmd_mktemp']:
        # create directory using mktemp command
        tmpdir, _, _ = proc.run([config['cmd_mktemp'], '-d'])
        tmpdir = tmpdir.rstrip('\n')
    else:
        # emulate mktemp
        tmpdir = remote.path.join(config['fs_fallback_tmpdir'],
                                  'remand-' + hexlify(os.urandom(randbytes)))

        remote.mkdir(tmpdir, mode=mode)

    log.debug('Created temporary directory {}'.format(tmpdir))

    try:
        yield tmpdir
    finally:
        if delete:
            log.debug('Removing temporary directory {}'.format(tmpdir))
            remove_dir(tmpdir)


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
def symlink(src, dst):
    if dst.endswith('/'):
        raise NotImplementedError('Creating link inside directory not '
                                  'implemented')
    lst = remote.lstat(dst)

    if lst:
        if not S_ISLNK(lst.st_mode):
            raise RemotePathIsNotALinkError('Already exists and not a link: '
                                            '{}'.format(dst))

        # remote is a link
        rsrc = remote.readlink(dst)
        if rsrc == src:
            return Unchanged(msg='Unchanged link: {} -> {}'.format(dst, src))

        # we need to update the link, unfortunately, this is often not possible
        # atomically
        remote.unlink(dst)
        remote.symlink(src, dst)
        return Changed(msg='Changed link: {} -> {} (previously -> {})'.format(
            dst, src, rsrc))

    remote.symlink(src, dst)
    return Changed(msg='Created link: {} -> {}'.format(dst, src))


@operation()
def touch(remote_path, mtime=None, atime=None):
    """Update mtime and atime of a path.

    Similar to running ``touch remote_path``.

    :param remote_path: Remote path whose times will get updated.
    :param mtime: New mtime. If ``None``, uses the current time.
    :param atime: New atime. Only used if ``mtime`` is not None. Defaults to
                  ``mtime``.
    :return: Since it always updates the current time, calling this function
             will always result in a modification.
    """
    # ensure the file exists
    if not remote.lstat(remote_path):
        with remote.file(remote_path, 'w') as out:
            out.write('')

    if mtime is None:
        remote.utime(remote_path, None)
        return Changed(msg=u'Touched {} to current time'.format(remote_path))
    else:
        atime = atime if atime is not None else mtime
        remote.utime(remote_path, (atime, mtime))
        return Changed(msg=u'Touched {} to mtime={}, atime={}'.format(
            remote_path, mtime, atime))


@operation()
def upload_file(local_path,
                remote_path=None,
                follow_symlink=True,
                create_parent=False):
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
    lst = os.stat(local_path) if follow_symlink else os.lstat(local_path)

    verifier = Verifier._by_short_name(config['fs_remote_file_verify'])()
    uploader = Uploader._by_short_name(config['fs_remote_file_upload'])()

    if lst is None:
        raise ConfigurationError(
            'Local file {!r} does not exist'.format(local_path))

    if S_ISLNK(lst.st_mode):
        # local file is a link
        rst = remote.lstat(remote_path)

        if rst:
            if not S_ISLNK(rst.st_mode):
                # remote file is not a link, unlink it
                remote.unlink(remote_path)
            elif remote.readlink(remote_path) != os.readlink(local_path):
                # non matching links
                remote.unlink(remote_path)
            else:
                # links pointing to the same target
                return Unchanged(
                    msg='Symbolink link up-to-date: {}'.format(remote_path))

        remote.symlink(os.readlink(local_path), remote_path)
        return Changed(msg='Created remote link: {}'.format(remote_path))

    if not st or not verifier.verify_file(st, local_path, remote_path):
        if create_parent:
            create_dir(remote.path.dirname(remote_path))

        uploader.upload_file(local_path, remote_path)

        if config.get_bool('fs_update_mtime'):
            times = (lst.st_mtime, lst.st_mtime)
            remote.utime(remote_path, times)
            log.debug('Updated atime/mtime: {}'.format(times))
        return Changed(msg='Upload {} -> {}'.format(local_path, remote_path))

    return Unchanged(msg='File up-to-date: {}'.format(remote_path))


@operation()
def upload_string(buf, remote_path, create_parent=False):
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
        if create_parent:
            create_dir(remote.path.dirname(remote_path))
        uploader.upload_buffer(buf, remote_path)
        return Changed(msg='Upload buffer ({}) -> {}'.format(
            len(buf), remote_path))

    return Unchanged(msg='File up-to-date: {}'.format(remote_path))


@operation()
def upload_tree(local_path, remote_path):
    # FIXME: think about implications regarding ownership, other attributes
    # FIXME: allow removing (sync)
    create_dir(remote_path)
    changed = False

    for dirpath, dirnames, filenames in os.walk(local_path):
        rel = os.path.relpath(dirpath, local_path)
        rem = remote.path.join(remote_path, rel)

        changed |= create_dir(rem).changed
        for fn in filenames:
            local_fn = os.path.join(dirpath, fn)
            remote_fn = remote.path.join(rem, fn)

            changed |= upload_file(
                local_fn, remote_fn, follow_symlink=False).changed

    if changed:
        return Changed(msg='Uploaded tree {} => {}'.format(
            local_path, remote_path))

    return Unchanged(msg='Tree already uploaded: {} => {}'.format(
        local_path, remote_path))


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
