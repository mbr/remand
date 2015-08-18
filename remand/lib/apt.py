from collections import OrderedDict, namedtuple
from datetime import datetime, timedelta

from debian.deb822 import Deb822
from remand import log, remote
from remand.exc import RemoteFailureError
from remand.lib import proc, memoize, fs
from remand.operation import operation, Unchanged, Changed
import times

PackageRecord = namedtuple('PackageRecord', 'name,version')


def _timestamp_to_datetime(rfn):
    st = remote.stat(rfn)
    if not st:
        ts = 0
    else:
        ts = st.st_mtime

    return times.to_universal(ts)


def _get_remand_update_stamp():
    UPDATE_FILE = '/var/lib/remand/last-apt-update'

    fs.create_dir(remote.path.dirname(UPDATE_FILE), 0o755)
    return UPDATE_FILE


@memoize()
def info_last_update():
    # note: may be inaccurate, if the necessary hooks are not set
    return max(
        _timestamp_to_datetime(_get_remand_update_stamp()),
        _timestamp_to_datetime('/var/lib/apt/periodic/update-success-stamp'),
        _timestamp_to_datetime('/var/lib/apt/periodic/update-stamp'))


@memoize()
def info_last_upgrade():
    # note: may be inaccurate, if the necessary hooks are not set
    return _timestamp_to_datetime('/var/lib/apt/periodic/upgrade-stamp')


@memoize()
def info_installed_packages():
    stdout, _, _ = proc.run(['dpkg-query', '--show'])

    pkgs = {}

    for line in stdout.splitlines():
        rec = PackageRecord(*line.split('\t'))
        pkgs[rec.name] = rec

    return pkgs


@operation()
def update(max_age=60 * 60):
    now = times.now()

    if max_age:
        current_age = now - info_last_update()
        if current_age < timedelta(seconds=max_age):
            return Unchanged(
                msg='apt cache is only {:.0f} minutes old, not updating'
                .format(current_age.total_seconds() / 60))

    proc.run(['apt-get', 'update'])

    # modify update stamp
    fs.touch(_get_remand_update_stamp())
    info_last_update.update_cache(datetime.utcnow())

    return Changed(msg='apt cache updated')


@operation()
def query_cache(pkgs):
    stdout, _, _ = proc.run(['apt-cache', 'show'] + list(pkgs))
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

    return Unchanged(pkgs)


@operation()
def install_packages(pkgs):
    proc.run(
        ['apt-get',
         'install',
         '--quiet',
         '--yes',  # options below don't work. why?
         #'--option', 'Dpkg::Options::="--force-confdef"',
         #'--option', 'Dpkg::Options::="--force-confold"'
         ] + list(pkgs),
        extra_env={
            'DEBIAN_FRONTEND': 'noninteractive',
        })

    # FIXME: detect if packages were installed?
    return Changed(msg='Installed {}'.format(' '.join(pkgs)))
