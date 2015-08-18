from functools import wraps

import pytest


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

            if isinstance(result, Failed):
                result._reraise()

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
    assert val.message is None


def test_harmless_operation_with_message():
    @operation()
    def does_nothing():
        return Unchanged(message='test')

    val = does_nothing()

    assert isinstance(val, Unchanged)
    assert val.value is None
    assert val.message == 'test'


def test_harmless_operation_with_value():
    @operation()
    def does_nothing():
        return 'four'

    val = does_nothing()

    assert isinstance(val, Unchanged)
    assert val.value is 'four'
    assert val.message is None


def test_harmless_operation_with_value_and_message():
    @operation()
    def does_nothing():
        return Unchanged('four', 'test')

    val = does_nothing()

    assert isinstance(val, Unchanged)
    assert val.value is 'four'
    assert val.message == 'test'


def test_changing_operation():
    @operation()
    def does_nothing():
        return Changed()

    val = does_nothing()

    assert isinstance(val, Changed)
    assert val.value is None
    assert val.message is None


def test_changing_operation_with_message():
    @operation()
    def does_nothing():
        return Changed(message='test')

    val = does_nothing()

    assert isinstance(val, Changed)
    assert val.value is None
    assert val.message == 'test'


def test_changing_operation_with_value():
    @operation()
    def does_nothing():
        return Changed('four')

    val = does_nothing()

    assert isinstance(val, Changed)
    assert val.value is 'four'
    assert val.message is None


def test_changing_operation_with_value_and_message():
    @operation()
    def does_nothing():
        return Changed('four', 'test')

    val = does_nothing()

    assert isinstance(val, Changed)
    assert val.value is 'four'
    assert val.message == 'test'


def test_failure_operation_raises():
    @operation()
    def oh_oh():
        raise RuntimeError('damn')

    with pytest.raises(RuntimeError) as exc_info:
        oh_oh()

    assert exc_info.value.message == 'damn'


def test_failure_operation_raises_on_failure_return():
    @operation()
    def oh_oh_ret():
        return Failed(RuntimeError('damn'))

    with pytest.raises(RuntimeError) as exc_info:
        oh_oh_ret()

    assert exc_info.value.message == 'damn'
