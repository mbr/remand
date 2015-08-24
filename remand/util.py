from functools import partial

import hashlib

from stuf.collects import ChainMap


class TypeConversionMixin(object):
    BOOLEAN_TRUE = ('1', 'yes', 'true', 'on')
    BOOLEAN_FALSE = ('0', 'no', 'false', 'off')

    def get_bool(self, key, default=None):
        rv = self[key]

        if rv in self.BOOLEAN_TRUE:
            return True

        if rv in self.BOOLEAN_FALSE:
            return False

        return default


class TypeConversionChainMap(TypeConversionMixin, ChainMap):
    pass


def validate_umask(umask):
    if not isinstance(umask, int):
        raise ValueError('Not an integer umask: {}'.format(umask))
    if umask > 0777:
        raise ValueError('Invalid umask value: {}'.format(umask))


def hash_file(file_obj, hashfunc=hashlib.sha1, bufsize=None):
    # hash local file
    m = hashfunc()

    if bufsize is None:
        from . import config
        bufsize = int(config['buffer_size'])

    # read full file in buffer sized chunks
    for chunk in iter(partial(file_obj.read, bufsize), b''):
        m.update(chunk)

    return m
