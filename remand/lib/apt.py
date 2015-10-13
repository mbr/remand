from collections import OrderedDict, namedtuple
import os
import time

from debian.deb822 import Deb822
from remand import log, remote, config
from remand.exc import RemoteFailureError
from remand.lib import proc, memoize, fs
from remand.operation import operation, Unchanged, Changed

PackageRecord = namedtuple('PackageRecord', 'name,version')


class CachedRemoteTimestamp(object):
    def __init__(self, rpath):
        self.rpath = rpath
        self.synced = False

    def sync(self):
        log.debug('Syncing timestamp {}'.format(self.rpath))
        if self.synced:
            log.debug('Timestamp already synced')
            return

        # ensure directory for timestamp exists
        if fs.create_dir(remote.path.dirname(self.rpath), 0o755).changed:
            # had to create directory, new timestamp
            self.synced = True
            self._current = 0
            log.debug('Timestamp did not exist')
            return

        # directory already exists
        st = remote.stat(self.rpath)
        if not st:
            # file does not exist
            self._current = 0
            log.debug('Timestamp did not exist')
        else:
            self._current = st.st_mtime
            log.debug('Timestamp synced to {}'.format(self._current))
        self.synced = True

    @property
    def current(self):
        self.sync()
        return self._current

    def set(self, timestamp=None):
        # ensure directory for timestamp exists
        fs.create_dir(remote.path.dirname(self.rpath), 0o755)

        # update timestamp
        fs.touch(self.rpath, timestamp)

        # update cached values
        if timestamp is not None:
            self._current = timestamp
            self.synced = True
        log.debug('Timestamp {} set to {}'.format(self.rpath, self._current))

    def get_age(self):
        self.sync()

        age = time.time() - self._current
        log.debug('Timestamp age ({}): {}'.format(self.rpath, age))
        return age

    def mark_current(self):
        self.set(None)

    def mark_stale(self):
        self.set(0)


@memoize()
def info_update_timestamp():
    # note: /var/lib/apt/periodic may be inaccurate, if the necessary hooks are
    #       not set. for this reason, we just use our own file
    return CachedRemoteTimestamp('/var/lib/remand/last-apt-update')


@memoize()
def info_dpkg_architecture():
    stdout, _, _ = proc.run([config['cmd_dpkg'], '--print-architecture'])
    return stdout.strip()


@memoize()
def info_dpkg_foreign_architectures():
    stdout, _, _ = proc.run(
        [config['cmd_dpkg'], '--print-foreign-architectures'])
    return stdout.splitlines()


@memoize()
def info_installed_packages():
    stdout, _, _ = proc.run([config['cmd_dpkg_query'], '--show'])

    pkgs = {}

    for line in stdout.splitlines():
        rec = PackageRecord(*line.split('\t'))
        pkgs[rec.name] = rec

    return pkgs


@operation()
def update(max_age=3600):
    if max_age < 0:
        return Unchanged(msg='apt update disabled (max_age < 0).')

    ts = info_update_timestamp()

    if max_age:
        age = ts.get_age()
        if age < max_age:
            return Unchanged(
                msg='apt cache is only {:.0f} minutes old, not updating'
                .format(age / 60))

    proc.run([config['cmd_apt_get'], 'update'])

    # modify update stamp
    ts.mark_current()

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
def install_packages(pkgs, check_first=True, release=None, max_age=3600,
                     force=False):
    if check_first and set(pkgs) < set(info_installed_packages().keys()):
        return Unchanged(msg='Already installed: {}'.format(' '.join(pkgs)))

    update(max_age)

    args = [config['cmd_apt_get']]
    if release:
        args.extend(['-t', release])

    args.extend([
        'install',
        '--quiet',
        '--yes',  # FIXME: options below don't work. why?
        #'--option', 'Dpkg::Options::="--force-confdef"',
        #'--option', 'Dpkg::Options::="--force-confold"'
    ])
    if force:
        args.append('--force-yes')
    args.extend(pkgs)
    proc.run(args, extra_env={'DEBIAN_FRONTEND': 'noninteractive', })

    # FIXME: make this a decorator for info, add "change_invalides" decorator?
    info_installed_packages.invalidate_cache()

    # FIXME: detect if packages were installed?
    return Changed(msg='Installed {}'.format(' '.join(pkgs)))


@operation()
def remove_packages(pkgs, check_first=True, purge=False, max_age=3600):
    if check_first and not set(pkgs).intersection(set(info_installed_packages
                   ().keys())):
        return Unchanged(msg='Not installed: {}'.format(' '.join(pkgs)))

    update(max_age)

    args = [config['cmd_apt_get']]

    args.extend([
        'remove' if not purge else 'purge',
        '--quiet',
        '--yes',  # FIXME: options below don't work. why?
        #'--option', 'Dpkg::Options::="--force-confdef"',
        #'--option', 'Dpkg::Options::="--force-confold"'
    ])
    args.extend(pkgs)
    proc.run(args, extra_env={'DEBIAN_FRONTEND': 'noninteractive', })

    info_installed_packages.invalidate_cache()

    return Changed(msg='{} {}'.format(' '.join('Removed' if not purge
                   else 'Purged', pkgs)))


@operation()
def auto_remove(max_age=3600):
    update(max_age)  # FIXME: make max_age become a config setting, add a
                     #        with_config context manager

    args = [config['cmd_apt_get']]
    args.extend([
        'autoremove',
        '--quiet',
        '--yes',
    ])
    stdout, _, _ = proc.run(args, extra_env={'DEBIAN_FRONTEND':
        'noninteractive',
    })

    if '0 to remove' in stdout:
        return Unchanged(msg='No packages auto-removed')

    info_installed_packages.invalidate_cache()

    return Changed(msg='Some packages were auto-removed')


@operation()
def dpkg_install(paths, check=True):
    pkgs = paths
    if not hasattr(paths, 'keys'):
        pkgs = {}

        # determine package names from filenames
        for p in paths:
            fn = os.path.basename(p)
            pkgs[fn[:fn.index('_')]] = p

    # log names
    log.debug('Package names: ' + ', '.join('{} -> {}'.format(k, v) for k, v in
                                            pkgs.items()))

    if check:
        missing = []
        installed = info_installed_packages()

        for name in pkgs:
            if name not in installed:
                missing.append(name)
    else:
        missing = pkgs.keys()

    log.debug('Installing packages: {}'.format(missing))

    if not missing:
        return Unchanged('Packages {} already installed'.format(', '.join(
            pkgs.keys())))

    # FIXME: see above
    info_installed_packages.invalidate_cache()

    with fs.remote_tmpdir() as rtmp:
        # upload packages to be installed
        pkg_files = []
        for name in missing:
            fs.upload_file(pkgs[name])
            pkg_files.append(remote.path.join(rtmp, pkgs[name]))

        # install in a single dpkg install line
        # FIXME: add debconf default and such (same as apt)
        args = [config['cmd_dpkg'], '-i']
        args.extend(pkg_files)
        proc.run(args, extra_env={'DEBIAN_FRONTEND': 'noninteractive', })

    return Changed(msg='Installed packages {}'.format(', '.join(missing)))


@operation()
def dpkg_add_architecture(arch):
    archs = [info_dpkg_architecture()] + info_dpkg_foreign_architectures()

    if arch in archs:
        return Unchanged(msg='Architecture already enabled: {}'.format(arch))

    proc.run([config['cmd_dpkg'], '--add-architecture', arch])

    # invalidate caches
    info_dpkg_foreign_architectures.invalidate_cache()
    info_update_timestamp().mark_stale()
    return Changed(msg='New architecture added: {}'.format(arch))


@operation()
def install_preference(path, name=None):
    op = fs.upload_file(
        path,
        remote.path.join(config['apt_preferences_d'], name or
                         os.path.basename(path)),
        create_parent=True)

    if op.changed:
        info_update_timestamp().mark_stale()

    return op


@operation()
def install_source_list(path, name=None, main=False):
    if main:
        if name is not None:
            raise ValueError('Cannot provide name when uploading sources.list')

        op = fs.upload_file(path,
                            config['apt_sources_list'],
                            create_parent=True)

    else:
        op = fs.upload_file(
            path,
            remote.path.join(config['apt_sources_list_d'], name or
                             os.path.basename(path)),
            create_parent=True)

    if op.changed:
        info_update_timestamp().mark_stale()

    return op


@operation()
def upgrade(max_age=3600, force=False, dist_upgrade=False):
    # FIXME: should allow upgrading selected packages
    update(max_age)

    args = [config['cmd_apt_get']]

    # FIXME: check for upgrades first and output proper changed status
    args.extend([
        'upgrade' if not dist_upgrade else 'dist-upgrade',
        '--quiet',
        '--yes',
        # FIXME: options below don't work. why?
        #'--option', 'Dpkg::Options::="--force-confdef"',
        #'--option', 'Dpkg::Options::="--force-confold"'
    ])
    if force:
        args.append('--force-yes')
    proc.run(args, extra_env={'DEBIAN_FRONTEND': 'noninteractive', })

    info_installed_packages.invalidate_cache()

    return Changed(msg='Upgraded all packages')
