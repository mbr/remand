from functools import wraps


class OperationResult(object):
    changed = None

    def __init__(self, value=None, msg=None):
        self._value = value
        self.msg = msg

    @property
    def value(self):
        return self._value

    @classmethod
    def from_rv(self, val):
        if not isinstance(val, (tuple, list)):
            val = (val, )

        return self._from_rv(*val)

    @classmethod
    def _from_rv(self, result_type, value=None, msg=None):
        if isinstance(result_type, OperationResult):
            return result_type

        if result_type is True:
            return Changed(value, msg)

        if result_type is False or result_type is None:
            return Unchanged(value, msg)

        raise ValueError(
            'Operation returned invalid result: {}'.format(result_type))

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
                result = OperationResult.from_rv(f(*args, **kwargs))
            except Exception as e:
                result = Failed(e)

            return result

        return _

    return wrapper


@operation()
def install_foobar(fail=None, change=None, success=None):
    if fail:
        raise RuntimeError('failed due to {}'.format(fail))

    if change:
        return True, change

    if success:
        return False, success, 'Great success'

    return False


def test_foo():
    pass
