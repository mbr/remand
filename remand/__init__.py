from __future__ import absolute_import

from contextlib import contextmanager
from functools import partial

#import pluginbase

#plugin_base = pluginbase.PluginBase(package='remand.plugins')

# globals
from werkzeug.local import LocalStack, LocalProxy


def _lookup_context(name):
    top = _context.top
    if top is None:
        raise RuntimeError('No current context. Did you forget to put your '
                           'module code inside a run() method?')
    return top[name]


_context = LocalStack()
remote = LocalProxy(partial(_lookup_context, 'remote'))
config = LocalProxy(partial(_lookup_context, 'config'))
log = LocalProxy(partial(_lookup_context, 'log'))
info = LocalProxy(partial(_lookup_context, 'info'))


@contextmanager
def remote_socket():
    import socket as mod_s
    from .remotes import monkey_socket as monkey_s

    old_attrs = {}

    # save old functions/attributes, then money_patch
    for name in monkey_s.__all__:
        if hasattr(mod_s, name):
            old_attrs[name] = getattr(mod_s, name)
        setattr(mod_s, name, getattr(monkey_s, name))

    yield

    # restore original functions/attributes. remove those added
    for name in monkey_s.__all__:
        if name in old_attrs:
            setattr(mod_s, name, old_attrs[name])
        else:
            delattr(mod_s, name)
