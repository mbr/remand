from functools import partial
import sys

import hashlib
import inflection

from stuf.collects import ChainMap

if sys.version_info.major < 3:
    from backports.configparser import ConfigParser
else:
    from configparser import ConfigParser


class TypeConversionMixin(object):
    BOOLEAN_TRUE = ('1', 'yes', 'true', 'on')
    BOOLEAN_FALSE = ('0', 'no', 'false', 'off')

    def get_bool(self, key, default=None):
        if key not in self:
            return default

        rv = self[key]

        if rv in self.BOOLEAN_TRUE:
            return True

        if rv in self.BOOLEAN_FALSE:
            return False

        raise ValueError('Not a valid boolean value: {}'.format(rv))


class TypeConversionChainMap(TypeConversionMixin, ChainMap):
    # backport of Py3 feature
    def new_child(self, m=None):
        return self.__class__({} if m is None else m, *self.maps)


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


def plural_n(word, times=2):
    if times == 1:
        return word
    return inflection.pluralize(word)
