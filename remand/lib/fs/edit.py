import re

from remand import util, log


class EditableFile(object):
    linesep = '\n'
    trailing_newline = True

    def __init__(self, name):
        self.name = name
        self.initial_hash = self._get_hash()
        log.debug('{} before editing: {}'.format(
            self.name, self.initial_hash.hexdigest()))

    def _get_hash(self):
        with self.open('rb') as f:
            return util.hash_file(f)

    def comment_out(self, regexp, prefix='# '):
        lines = []
        for line in self.lines():
            if re.search(regexp, line) and not line.startswith(prefix):
                lines.append(prefix + line)
            else:
                lines.append(line)
        self.set_lines(lines)

    def lines(self):
        with self.open('r') as f:
            ls = f.read().split(self.linesep)

            # keep the trailing newline
            if self.trailing_newline and not ls[-1]:
                ls.pop()
            return ls

    def set_lines(self, lines):
        with self.open('w') as f:
            if self.trailing_newline:
                lines = lines + ['']

            f.write(self.linesep.join(lines))

    def insert_line(self, line, pos=None, duplicate=False):
        lines = self.lines()
        if not duplicate and line in lines:
            return

        if pos is None:
            lines.append(line)
        else:
            lines.insert(pos, line)

        self.set_lines(lines)

    @property
    def modified(self):
        h = self._get_hash()
        log.debug('{} hash currently: {}'.format(self.name, h.hexdigest()))
        return self.initial_hash.digest() != h.digest()

    def open(self, *args, **kwargs):
        return open(self.name, *args, **kwargs)
