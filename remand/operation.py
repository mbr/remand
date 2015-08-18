from functools import wraps

import logbook

log = logbook.Logger('op')


def operation():
    def wrapper(f):
        @wraps(f)
        def _(*args, **kwargs):
            try:
                rv = f(*args, **kwargs)
                if isinstance(rv, OperationResult):
                    result = rv
                else:
                    result = Unchanged(value=rv)
            except Exception as e:
                result = Failed(e)

            # log results
            if isinstance(Failed, result):
                log.error(str(result.exc))
            elif isinstance(Changed, result):
                log.info(result.msg or 'changed: {}'.format(f.__name__))
            elif isinstance(Unchanged, result):
                log.debug(result.msg or 'unchanged: {}'.format(f.__name__))

            if isinstance(result, Failed):
                result._reraise()

            return result

        return _

    return wrapper


class OperationResult(object):
    changed = None

    def __init__(self, value=None, message=None):
        self._value = value
        self.message = message

    @property
    def value(self):
        return self._value

    def __str__(self):
        return repr(self)

    def __repr__(self):
        return '{}({!r}, {!r})'.format(self.__class__.__name__, self._value,
                                       self.message)


class Changed(OperationResult):
    changed = True


class Unchanged(OperationResult):
    changed = False


class Failed(OperationResult):
    def __init__(self, exc):
        self.exc = exc
        self.message = str(exc)

    def value(self):
        self._reraise()

    def _reraise(self):
        raise self.exc  # from self.exc

    def __repr__(self):
        return '{}({!r})'.format(self.__class__.__name__, self.exc)
