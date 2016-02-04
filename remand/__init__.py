from functools import partial, wraps
from werkzeug.local import LocalStack, LocalProxy


def _lookup_context(name):
    top = _context.top
    if top is None:
        raise RuntimeError('No current context. Did you forget to put your '
                           'module code inside a run() method?')
    return top[name]


def keep_context(f):
    # allows keeping a context that is thread local between threads
    snapshot = _context.top.copy()

    @wraps(f)
    def _(*args, **kwargs):
        _context.push(snapshot)
        return f(*args, **kwargs)

    return _


_context = LocalStack()
remote = LocalProxy(partial(_lookup_context, 'remote'))
config = LocalProxy(partial(_lookup_context, 'config'))
log = LocalProxy(partial(_lookup_context, 'log'))
info = LocalProxy(partial(_lookup_context, 'info'))
current_plan = LocalProxy(partial(_lookup_context, 'current_plan'))

# public API:

# warning: wacky circular import
from .plan import Plan

__all__ = ['remote', 'config', 'log', 'info', 'current_plan', 'Plan']
