import hashlib
import os

from remand import remote, config, log
from remand.exc import ConfigurationError
from remand.lib import proc


def _hash_file(hashfunc, fp):
    m = hashfunc()

    while True:
        buf = fp.read(int(config['buffer_size']))
        if not buf:
            break
        m.update(buf)

    return m


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

