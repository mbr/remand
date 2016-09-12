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
            raise ConfigurationError(
                'Not a valid info entry (must be `module.name`): {}'.format(k))
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
                funcname, modname))

        return func()


def memoize(key=None):
    def wrapper(f):
        name = key or '__memoize_{}.{}'.format(f.__module__, f.__name__)

        @wraps(f)
        def _(*args):
            sig = (name, ) + args
            if config.get_bool('info_cache') and sig in info.cache:
                v = info.cache[sig]
                log.debug('Memoize cache hit {}'.format(sig))
            else:
                v = f(*args)
                log.debug('Memoize cache miss {}'.format(sig))
                info.cache[sig] = v
            return v

        def update_cache(value, *args):
            sig = (name, ) + args
            info.cache[sig] = value

        def invalidate_cache(*args):
            sig = (name, ) + args
            if sig in info.cache:
                del info.cache[sig]

        _.update_cache = update_cache
        _.invalidate_cache = invalidate_cache
        return _

    return wrapper
