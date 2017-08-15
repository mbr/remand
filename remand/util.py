from fcntl import fcntl, F_GETFL, F_SETFL
from functools import partial
import os
import sys
import threading

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


def indent(prefix, s):
    return prefix + ('\n' + prefix).join(line for line in s.splitlines())


# unused:
# def set_non_blocking(f):
#     if hasattr(f, 'fileno'):
#         f = f.fileno()

#     flags = fcntl(f, F_GETFL)
#     fcntl(f, F_SETFL, flags | os.O_NONBLOCK)


class CollectThread(threading.Thread):
    def __init__(self, input_source, *args, **kwargs):
        super(CollectThread, self).__init__(*args, **kwargs)
        self.buffer = []
        self.input_source = input_source
        self.setDaemon(True)
        self.start()

    def get_result(self):
        if isinstance(self.buffer[0], Exception):
            raise self.buffer[0]
        else:
            return self.buffer[0]

    def run(self):
        try:
            self.buffer.append(self.input_source.read())
        except Exception as e:
            self.buffer.append(e)
        finally:
            self.input_source.close()


def write_all(dest, input, bufsize=4096):
    if hasattr(input, 'read'):
        for chunk in iter(partial(input.read, bufsize), ''):
            dest.write(chunk)
        # log.debug('write_all: Chunk sent')
    else:
        # log.debug('write_all: Input sent')
        dest.write(input)


def any_changed(*args):
    return any(map(lambda res: res.changed, args))


def parse_dotenv(buf):
    return dict(
        line.split('=', 1) for line in buf.splitlines()
        if line.strip() and not line.strip().startswith('#'))
