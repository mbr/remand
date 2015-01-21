from stat import S_ISDIR, S_ISLNK, S_ISREG
import os

from remand import remote, config, log
from remand.exc import ConfigurationError, RemoteFailureError

from remand.status import changed, unchanged

from .verify import Verifier
from .upload import Uploader


def _expand_remote_dest(local_path, remote_path):
    if remote_path is None:
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
            # if it's a directory, correct path
            remote_path = remote.path.join(remote_path,
                                           remote.path.basename(local_path))

            st = remote.lstat(remote_path)
            log.debug('Expanded remote_path to {!r}'.format(remote_path))

    # ensure st is either non-existant, or a regular file
    if st and not S_ISREG(st.st_mode):
        raise RemoteFailureError(
            'Not a regular file: {!r}'.format(remote_path)
        )
    return st, remote_path


def create_dir(path, mode=0777):
    """Ensure that a directory exists at path. Parent directories are created
    if needed.

    :param path: Directory to create if it does not exist.
    :param mode: Mode for newly created parent directories.
    """
    npath = remote.path.normpath(path)

    st = remote.stat(path)

    if not st:
        head, tail = remote.path.split(path)
        if tail and head:
            # create parent directories
            create_dir(head, mode)
        remote.mkdir(npath, mode)
        changed('Created directory: {}'.format(path))
    else:
        unchanged('Already exists: {}'.format(path))


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
    """
    st, remote_path = _expand_remote_dest(local_path, remote_path)

    verifier = Verifier._by_short_name(config['fs_remote_file_verify'])()
    uploader = Uploader._by_short_name(config['fs_remote_file_upload'])()

    if not os.path.exists(local_path):
        raise ConfigurationError('Local file {!r} does not exist'.format(
            local_path)
        )

    if not st or not verifier.verify_file(st, local_path, remote_path):
        uploader.upload_file(local_path, remote_path)
        if config.get_bool('fs_update_mtime'):
            lst = os.stat(local_path)
            times = (lst.st_mtime, lst.st_mtime)
            remote.utime(remote_path, times)
            log.debug('Updated atime/mtime: {}'.format(times))
        changed('Upload {} -> {}'.format(local_path, remote_path))
    else:
        unchanged('File up-to-date: {}'.format(remote_path))
