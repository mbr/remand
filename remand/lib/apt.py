from collections import OrderedDict, namedtuple
from datetime import datetime, timedelta
import os

from debian.deb822 import Deb822
from remand import log, remote, config
from remand.exc import RemoteFailureError
from remand.lib import proc, memoize, fs
from remand.operation import operation, Unchanged, Changed, any_changed
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
    stdout, _, _ = proc.run([config['cmd_dpkg_query'], '--show'])

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

    proc.run([config['cmd_apt_get'], 'update'])

    # modify update stamp
    fs.touch(_get_remand_update_stamp())
    info_last_update.update_cache(datetime.utcnow())

    return Changed(msg='apt cache updated')


@operation()
def query_cache(pkgs):
    stdout, _, _ = proc.run([config['cmd_apt_cache'], 'show'] + list(pkgs))
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
def install_packages(pkgs, check_first=True, release=None):
    if check_first and set(pkgs) < set(info_installed_packages().keys()):
        return Unchanged(msg='Already installed: {}'.format(' '.join(pkgs)))

    args = [config['cmd_apt_get']]
    if release:
        args.extend(['-t', release])

    args.extend([
        'install',
        '--quiet',
        '--yes',  # FIXME: options below don't work. why?
        #'--option', 'Dpkg::Options::="--force-confdef"',
        #'--option', 'Dpkg::Options::="--force-confold"'
    ] + list(pkgs), )
    proc.run(args, extra_env={'DEBIAN_FRONTEND': 'noninteractive', })

    # FIXME: make this a decorator for info, add "change_invalides" decorator?
    info_installed_packages.invalidate_cache()

    # FIXME: detect if packages were installed?
    return Changed(msg='Installed {}'.format(' '.join(pkgs)))


@operation()
def install_preference(path, name=None):
    return fs.upload_file(
        path,
        remote.path.join(config['apt_preferences_d'], name or
                         os.path.basename(path)),
        create_parent=True)


@operation()
def install_source_list(path, name=None):
    return fs.upload_file(
        path,
        remote.path.join(config['apt_sources_list_d'], name or
                         os.path.basename(path)),
        create_parent=True)


@operation()
def install_source_lists(paths):
    if any_changed(*[install_source_list(path) for path in paths]):
        update(max_age=0)
        return Changed('added apt sources added and updated')
    return Unchanged()
