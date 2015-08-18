from functools import wraps


class OperationResult(object):
    changed = None

    def __init__(self, value=None, msg=None):
        self._value = value
        self.msg = msg

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
        raise self.exc  # from self.exc

    def __repr__(self):
        return '{}({!r})'.format(self.__class__.__name__, self.exc)


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

            return result

        return _

    return wrapper


@operation()
def return_four(fail_because=None, change=None):
    if fail_because:
        raise RuntimeError('failed due to {}'.format(fail_because))

    if change:
        return Changed(4, change)

    return 4


def test_harmless_operation():
    @operation()
    def does_nothing():
        pass

    val = does_nothing()

    assert isinstance(val, Unchanged)
    assert val.value is None
