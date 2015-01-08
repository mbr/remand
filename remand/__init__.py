from functools import partial

#import pluginbase

#plugin_base = pluginbase.PluginBase(package='remand.plugins')


# globals
from werkzeug.local import LocalStack, LocalProxy


def _lookup_context(name):
    top = _context.top
    if top is None:
        raise RuntimeError('No current context')
    return top[name]


_context = LocalStack()
transport = LocalProxy(partial(_lookup_context, 'transport'))
config = LocalProxy(partial(_lookup_context, 'config'))
log = LocalProxy(partial(_lookup_context, 'log'))
