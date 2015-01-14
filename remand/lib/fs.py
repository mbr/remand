from remand import remote
from remand.status import changed, unchanged


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
