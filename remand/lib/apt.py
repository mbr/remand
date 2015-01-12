from collections import OrderedDict

from debian.deb822 import Deb822
from remand import log
from remand.exc import RemoteFailureError
from remand.lib import proc


def query_packages(*pkgs):
    stdout, stderr = proc.run(['apt-cache', 'show'] + list(pkgs))
    pkgs = OrderedDict()
    for dump in stdout.split('\n\n'):
        # skip empty lines
        if not dump or dump.isspace():
            continue
        try:
            pkg_info = Deb822(dump)
        except ValueError:
            log.debug(dump)
            raise RemoteFailureError('Error parsing Deb822 info.')

        pkgs[pkg_info['Package']] = pkg_info

    return pkgs


def install_packages(*pkgs):
    proc.run(
        ['apt-get', 'install', '--quiet', '--yes',
         '--option', 'Dpkg::Options::="--force-confdef"',
         '--option', 'Dpkg::Options::="--force-confold"']
        + list(pkgs),
        extra_env={
            'DEBIAN_FRONTEND': 'noninteractive',
        }
    )
