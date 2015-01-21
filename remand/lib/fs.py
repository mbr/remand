import hashlib
from shutil import copyfileobj
from stat import S_ISDIR, S_ISLNK, S_ISREG
import os

from remand import remote, config, log
from remand.exc import ConfigurationError, RemoteFailureError
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


class Verifier(object):
    registry = {}

    def verify(self, st, local_path, remote_path):
        raise NotImplementedError

    @classmethod
    def _registered(cls, child):
        cls.registry[child.short_name] = child
        return child

    @classmethod
    def _by_short_name(cls, short_name):
        v = cls.registry.get(short_name, None)
        if v is None:
            raise ConfigurationError(
                'Unknown remote file verification method: {!r}. Check your '
                'fs_remote_*_verify configuration setting.'
                .format(short_name)
            )

        return cls.registry[short_name]

    def __str__(self):
        return 'Verifier<{}>'.format(self.short_name)


@Verifier._registered
class VerifierIgnore(Verifier):
    short_name = 'ignore'

    def verify(self, st, local_path, remote_path):
        return False


@Verifier._registered
class VerifierRead(Verifier):
    short_name = 'read'

    def verify(self, st, local_path, remote_path):
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


@Verifier._registered
class VerifierSHA(Verifier):
    short_name = 'sha1sum'

    def verify(self, st, local_path, remote_path):
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


@Verifier._registered
class VerifierStat(Verifier):
    short_name = 'stat'

    def verify(self, st, local_path, remote_path):
        lst = os.stat(local_path)

        mul = int(config['fs_mtime_multiplier'])

        # we cast to int, to avoid into issues with different mtime resolutions
        l = (int(lst.st_mtime * mul), lst.st_size)
        r = (int(st.st_mtime * mul), st.st_size)
        log.debug('stat (mtime/size): local {}/{}, remote {}/{}'
                  .format(*(l + r)))
        return l == r


@Verifier._registered
class VerifierRSync(Verifier):
    short_name = 'rsync'


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

    upload = config['fs_remote_file_upload']

    verifier = Verifier._by_short_name(config['fs_remote_file_verify'])()

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

    log.debug('verify/upload: {}/{}'.format(
        verifier, uploader)
    )

    if not os.path.exists(local_path):
        raise ConfigurationError('Local file {!r} does not exist'.format(
            local_path)
        )

    if not st or not verifier.verify(st, local_path, remote_path):
        uploader(local_path, remote_path)
        if config.get_bool('fs_update_mtime'):
            lst = os.stat(local_path)
            times = (lst.st_mtime, lst.st_mtime)
            remote.utime(remote_path, times)
            log.debug('Updated atime/mtime: {}'.format(times))
        changed('Upload {} -> {}'.format(local_path, remote_path))
    else:
        unchanged('File up-to-date: {}'.format(remote_path))
