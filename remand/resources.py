import os


class ResourceHandler(object):
    def __init__(self, path=None):
        self.path = path or []

    def push_directory(self, directory):
        self.path.insert(0, directory)

    def push_module(self, mod):
        self.add_directory(os.path.dirname(mod.__file__))

    def pop(self):
        return self.path.pop(0)

    def _first_found(self, name, subdir=None):
        if not name.startswith('/'):
            raise ValueError('Path must be absolute')

        subpath = name.lstrip('/')

        if subdir:
            subpath = os.path.join(subdir, subpath)

        for p in self.path:
            cur = os.path.join(p, subpath)
            if os.path.exists(cur):
                return cur

        raise IOError('No file named {!r} found in search path: {!r}'
                      .format(subpath, self.path))

    def get_file(self, name):
        return self._first_found(name, 'files')

    def __repr__(self):
        return '{}({!})'.format(self.__class__.__name__, self.path)
