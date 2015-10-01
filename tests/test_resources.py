import pytest
import os

from remand.resources import ResourceHandler

RES = os.path.join(os.path.dirname(__file__), 'resources')


@pytest.fixture()
def r():
    r = ResourceHandler([os.path.join(RES, p) for p in ('B', 'C')])
    r.push_directory(os.path.join(RES, 'A'))
    return r


def test_simple_handling(r):
    assert r.get_file('/1') == os.path.join(RES, 'A', 'files', '1')
    assert r.get_file('/2') == os.path.join(RES, 'B', 'files', '2')
    assert r.get_file('/3') == os.path.join(RES, 'C', 'files', '3')


def test_pop(r):
    r.pop()
    assert r.get_file('/1') == os.path.join(RES, 'B', 'files', '1')


def test_raises_on_missing(r):
    with pytest.raises(IOError):
        assert r.get_file('/4')


def test_raises_on_relative(r):
    with pytest.raises(ValueError):
        assert r.get_file('1')
