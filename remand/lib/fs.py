from functools import reduce

from remand import remote
from remand.status import changed, unchanged


def _path_components(path):
    """Inverse of path.join.

    >>> _path_components('/a/b/c')
    ['/', 'a', 'b', 'c']
    """
    head = remote.path.normpath(path)
    acc = []

    while True:
        head, tail = remote.path.split(head)
        if not tail:
            acc.insert(0, head)
            break
        acc.insert(0, tail)

    return acc


def _subpaths(path):
    """Returns all subpaths leading up to a path:

    >>> _subpaths('/a/b/c')
    ['/', '/a', '/a/b', '/a/b/c']
    """
    comps = _path_components(path)
    return reduce(lambda acc, comp: acc + [remote.path.join(acc[-1], comp)],
                  comps,
                  [comps.pop(0)])


def directory(path, mode=0777):
    """Ensure that a directory exists at path. Parent directories are created
    if needed.

    :param path: Directory to create if it does not exist.
    :param mode: Mode for newly created parent directories.
    """
    npath = remote.path.normpath(path)

    st = remote.stat(path)

    if not st:
        head, tail = remote.path.split(path)
        if tail and head:
            # create parent directories
            directory(head, mode)
        remote.mkdir(npath, mode)
        changed('Created directory: {}'.format(path))
    else:
        unchanged('Already exists: {}'.format(path))
