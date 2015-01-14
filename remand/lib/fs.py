import hashlib
from shutil import copyfileobj
from stat import S_ISDIR

from remand import remote, config, log
from remand.exc import ConfigurationError
from remand.lib import proc
from remand.status import changed, unchanged


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


def _hash_file(hashfunc, fp):
    m = hashfunc()

    while True:
        buf = fp.read(int(config['buffer_size']))
        if not buf:
            break
        m.update(buf)

    return m


class _FileUploader(object):
    def _examine_remote(self, local_path, remote_path):
        if remote_path is None:
            remote_path = local_path

        st = remote.stat(remote_path)
        if st and S_ISDIR(st.st_mode):
            # if it's a directory, correct path and try again
            remote_path = remote.path.join(remote_path,
                                           remote.path.basename(local_path))
            st = remote.stat(remote_path)

        if st:
            log.debug('Already exists: {}'.format(remote_path))
        return remote_path, st

    def upload_file(self, local_path, remote_path=None):
        remote_path, st = self._examine_remote(local_path, remote_path)

        if st is None or self._needs_update(local_path, remote_path):
            self._put_file(local_path, remote_path)
            changed('Upload {} -> {}'.format(local_path, remote_path))
        else:
            unchanged('File up-to-date: {}'.format(remote_path))

    def _needs_update(self, local_path, remote_path):
        return True

    def _put_file(self, local_path, remote_path=None):
        with file(local_path, 'rb') as src,\
                remote.file(remote_path, 'wb') as dst:
            copyfileobj(src, dst)


class _Sha1FileUploader(_FileUploader):
    def _needs_update(self, local_path, remote_path=None):
        # hash local file
        with open(local_path, 'rb') as lfile:
            m = _hash_file(hashlib.sha1, lfile)

            # get remote hash
            stdout, _ = proc.run([config['cmd_sha1sum'], remote_path])
            remote_hash = stdout.split(None, 1)[0]

            log.debug('Local hash: {} Remote hash: {}'.format(
                m.hexdigest(), remote_hash
            ))

            return remote_hash != m.hexdigest()


def upload_file(local_path, remote_path=None):
    """Uploads a local file to a remote and if does not exist or differs
    from the local version, uploads it.

    To avoid having to transfer the file one or more times if unchanged,
    different methods for verification are available. These can be configured
    using the ``fs_remote_file_verify`` configuration variable.

    :param local_path: Local file to upload.
    :param remote_path: Remote name for the file. If ``None``, same as
                        ``local_path``. If it points to a directory, the file
                        will be uploaded to the directory.
    """
    uhandler = config['fs_remote_file_verify']
    if uhandler == 'rsync':
        raise NotImplementedError
    elif uhandler == 'sha1sum':
        uploader = _Sha1FileUploader()
    elif uhandler == 'read':
        raise NotImplementedError
    elif uhandler == 'ignore':
        uploader = _FileUploader()
    else:
        raise ConfigurationError(
            'Unknown remote file verification method: {!r}. Check your '
            'fs_remote_file_verify configuration setting.'
            .format(config['fs_remote_file_verify'])
        )
    log.debug('uhandler ({}): {}'.format(uhandler, uploader))
    uploader.upload_file(local_path, remote_path)
