from __future__ import absolute_import

from contextlib import contextmanager


@contextmanager
def remote_socket():
    import socket as mod_s
    from . import monkey_socket as monkey_s

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
