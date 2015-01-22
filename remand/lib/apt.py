from collections import OrderedDict
from datetime import datetime

from debian.deb822 import Deb822
from remand import log, remote
from remand.exc import RemoteFailureError
from remand.lib import proc


def _timestamp_to_datetime(rfn):
    st = remote.stat(rfn)
    if not st:
        ts = 0
    else:
        ts = st.st_mtime

    return datetime.fromtimestamp(ts)


def info_last_update():
    # note: may be inaccurate, if the necessary hooks are not set
    return max(
        _timestamp_to_datetime('/var/lib/apt/periodic/update-success-stamp'),
        _timestamp_to_datetime('/var/lib/apt/periodic/update-stamp')
    )


def info_last_upgrade():
    # note: may be inaccurate, if the necessary hooks are not set
    return _timestamp_to_datetime('/var/lib/apt/periodic/upgrade-stamp')


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
