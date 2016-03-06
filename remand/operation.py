from functools import wraps

import logbook

from .exc import RebootNeeded

log = logbook.Logger('op')


def any_changed(*changes):
    return any(c.changed for c in changes)


def operation():
    def wrapper(f):
        @wraps(f)
        def _(*args, **kwargs):
            log.debug('{}: start'.format(f.__name__))
            try:
                rv = f(*args, **kwargs)
                if isinstance(rv, OperationResult):
                    result = rv
                else:
                    result = Unchanged(value=rv)
            except Exception as e:
                result = Failed(e)

            # log results
            if isinstance(result, Failed):
                log.exception(result.exc)
            elif isinstance(result, Changed):
                log.info(result.msg or '{}: changed'.format(f.__name__))
            elif isinstance(result, Unchanged):
                log.debug(result.msg or '{}: unchanged'.format(f.__name__))

            if isinstance(result, Failed):
                result._reraise()

            # handle reboot
            if result.reboot_needed:
                raise RebootNeeded(f.__name__)

            return result

        return _

    return wrapper


class OperationResult(object):
    changed = None

    def __init__(self, value=None, msg=None, reboot_needed=False):
        self._value = value
        self.msg = msg
        self.reboot_needed = reboot_needed

    @property
    def value(self):
        return self._value

    def __str__(self):
        return repr(self)

    def __repr__(self):
        return '{}({!r}, {!r})'.format(self.__class__.__name__, self._value,
                                       self.msg)


class Changed(OperationResult):
    changed = True


class Unchanged(OperationResult):
    changed = False


class Failed(OperationResult):
    def __init__(self, exc):
        self.exc = exc
        self.msg = str(exc)

    def value(self):
        self._reraise()

    def _reraise(self):
        raise self.exc  # from self.exc

    def __repr__(self):
        return '{}({!r})'.format(self.__class__.__name__, self.exc)
