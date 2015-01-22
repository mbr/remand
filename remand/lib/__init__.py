from functools import wraps
from importlib import import_module

from remand import log, info, config
from remand.exc import ConfigurationError


class InfoManager(object):
    def __init__(self):
        self.cache = {}

    def __getitem__(self, k):
        """Retrieve a piece of information.

        :param k: Name
        """
        try:
            modname, funcname = k.rsplit('.', 1)
        except ValueError:
            raise ConfigurationError('Not a valid name: {}'.format(k))
        funcname = 'info_{}'.format(funcname)
        modname = 'remand.lib.{}'.format(modname)

        # ensure module is imported
        try:
            mod = import_module(modname)
        except ImportError:
            raise ConfigurationError('Python module not found: {}'
                                     .format(modname))

        func = getattr(mod, funcname, None)

        if func is None:
            raise ConfigurationError('Missing callable {} in {}'.format(
                funcname, modname
            ))

        return func()


def memoize(key=None):
    def wrapper(f):
        name = key or '__memoize_{}.{}'.format(f.__module__, f.__name__)

        @wraps(f)
        def _(*args):
            sig = (name,) + args
            if config.get_bool('info_cache') and sig in info.cache:
                v = info.cache[sig]
                log.debug('Memoize cache hit ({}): {}'.format(sig, v))
            else:
                v = f(*args)
                log.debug('Memoize cache miss ({}): {}'.format(sig, v))
                info.cache[sig] = v
            return v

        _.memoize_key = name
        return _
    return wrapper
