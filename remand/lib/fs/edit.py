from remand import util, log


class EditableFile(object):
    def __init__(self, name):
        self.name = name
        self.initial_hash = self._get_hash()
        log.debug('{} before editing: {}'.format(
            self.name, self.initial_hash.hexdigest()))

    def _get_hash(self):
        with self.open('rb') as f:
            return util.hash_file(f)

    def open(self, *args, **kwargs):
        return open(self.name, *args, **kwargs)

    @property
    def modified(self):
        h = self._get_hash()
        log.debug('{} hash currently: {}'.format(self.name, h.hexdigest()))
        return self.initial_hash.digest() != h.digest()
