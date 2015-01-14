import hashlib
from shutil import copyfileobj
from stat import S_ISDIR
import os

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


def _upload_write(local_path, remote_path):
    with file(local_path, 'rb') as src,\
            remote.file(remote_path, 'wb') as dst:
        copyfileobj(src, dst)


def _verify_read(st, local_path, remote_path):
    with remote.file(remote_path, 'rb') as rf,\
            file(local_path, 'rb') as lf:

        # enable prefetching if files support it
        # otherwise, performance is horrible (like disabled pipelining)
        if hasattr(rf, 'prefetch'):
            rf.prefetch()

        bufsize = int(config['buffer_size'])
        while True:
            rbuf = rf.read(bufsize)
            lbuf = lf.read(bufsize)

            if rbuf != lbuf:
                return False

            # if both files end at the same time, we're good
            if rbuf == lbuf == '':
                return True


def _verify_sha(st, local_path, remote_path):
    # hash local file
    with open(local_path, 'rb') as lfile:
        m = _hash_file(hashlib.sha1, lfile)

        # get remote hash
        stdout, _ = proc.run([config['cmd_sha1sum'], remote_path])
        remote_hash = stdout.split(None, 1)[0]

        log.debug('Local hash: {} Remote hash: {}'.format(
            m.hexdigest(), remote_hash
        ))

        return remote_hash == m.hexdigest()


def _verify_stat(st, local_path, remote_path):
    lst = os.stat(local_path)

    mul = int(config['fs_mtime_multiplier'])

    # we cast to int, to avoid into issues with different mtime resolutions
    l = (int(lst.st_mtime * mul), lst.st_size)
    r = (int(st.st_mtime * mul), st.st_size)
    log.debug('stat (mtime/size): local {}/{}, remote {}/{}'.format(*(l + r)))
    return l == r


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
    verify = config['fs_remote_file_verify']
    upload = config['fs_remote_file_upload']

    if verify == 'stat':
        verifier = _verify_stat
    elif verify == 'rsync':
        raise NotImplementedError('rsync-verify is currently not implemented')
    elif verify == 'sha1sum':
        verifier = _verify_sha
    elif verify == 'read':
        verifier = _verify_read
    elif verify == 'ignore':
        verifier = lambda: False
    else:
        raise ConfigurationError(
            'Unknown remote file verification method: {!r}. Check your '
            'fs_remote_file_verify configuration setting.'
            .format(config['fs_remote_file_verify'])
        )

    if upload == 'write':
        uploader = _upload_write
    elif upload == 'rsync':
        raise NotImplementedError('rsync-upload is currently not implemented')
    else:
        raise ConfigurationError(
            'Unknown upload method: {!r}. Check your '
            'fs_remote_file_upload configuration setting.'
            .format(config['fs_remote_file_upload'])
        )

    log.debug('verify/upload ({}/{}): {}/{}'.format(
        verify, upload, verifier, uploader)
    )

    if not os.path.exists(local_path):
        raise ConfigurationError('Local file {!r} does not exist'.format(
            local_path)
        )

    if remote_path is None:
        remote_path = local_path

    st = remote.stat(remote_path)
    if st and S_ISDIR(st.st_mode):
        # if it's a directory, correct path and try again
        remote_path = remote.path.join(remote_path,
                                       remote.path.basename(local_path))
        st = remote.stat(remote_path)

    if not st or not verifier(st, local_path, remote_path):
        uploader(local_path, remote_path)
        if config.get_bool('fs_update_mtime'):
            lst = os.stat(local_path)
            times = (lst.st_mtime, lst.st_mtime)
            remote.utime(remote_path, times)
            log.debug('Updated atime/mtime: {}'.format(times))
        changed('Upload {} -> {}'.format(local_path, remote_path))
    else:
        unchanged('File up-to-date: {}'.format(remote_path))
