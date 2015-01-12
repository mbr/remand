from collections import OrderedDict

from remand import remote, log
from remand.exc import RemoteFailureError
from remand.lib import proc


class PackageInfo(object):
    def __init__(self):
        self.fields = {}

    @property
    def name(self):
        return self.fields['Package']

    @classmethod
    def from_dump(cls, s):
        pkg = cls()
        prev_field = None
        for line in s.splitlines():
            # skip empty lines
            if line.isspace():
                continue

            # check if the line is a continuation
            if line.startswith(' '):
                # if we did not see a previous field, it's an error
                if prev_field is None:
                    log.debug(s)
                    raise RemoteFailureError('Unexpected continuation in '
                                             'apt-cache output')

                # strip leading space
                line = line[1:]

                if line == '.':
                    # a single dot is just a paragraph break
                    line = ''

                pkg.fields[prev_field] += '\n' + line
                continue

            # no continuation
            parts = line.split(': ', 1)

            if len(parts) != 2:
                raise RemoteFailureError('Badly formatted apt-line: {}'
                                         .format(line))
            pkg.fields[parts[0]] = parts[1]
            prev_field = parts[0]
        return pkg

    @classmethod
    def parse_dumplist(cls, dump):
        pkgs = OrderedDict()
        for pkg_dump in dump.split('\n\n'):
            if not pkg_dump.strip():
                continue  # skip empty dumps
            pkg = cls.from_dump(pkg_dump)
            pkgs[pkg.name] = pkg
        return pkgs


def query_packages(*pkgs):
    dump = proc.run(['apt-cache', 'show'] + list(pkgs))
    return PackageInfo.parse_dumplist(dump[0])
