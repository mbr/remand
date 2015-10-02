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
current_plan = LocalProxy(partial(_lookup_context, 'current_plan'))
