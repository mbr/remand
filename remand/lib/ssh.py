import os
import re

from remand import config, info, log, remote, util
from remand.lib import fs, posix, proc, systemd, memoize
from remand.operation import operation, Changed, Unchanged

from sshkeys import Key

OPENSSH_VERSION_RE = re.compile(r'^OpenSSH_(\d)+.(\d+)([^\s]+)')


class KeyFile(object):
    def __init__(self):
        self.keys = []

    def add(self, key):
        self.keys.append(key)

    def add_from_file(self, path):
        self.keys.append(Key.from_pubkey_file(path))

    def __str__(self):
        return ''.join(k.to_pubkey_line() + '\n' for k in self.keys)


# FIXME: needs a generic way to invalidate ("invalidated on .. software
#        install", "... on file upload")
# FIXME: example: memorize(..., invalidated_by=['pkg_install', 'fs_change'])
@memoize()
def info_openssh_version():
    stdout, stderr, rval = proc.run(['sshd', '-?'], status_ok='any')

    if rval == 1:
        m = OPENSSH_VERSION_RE.match(stderr.splitlines()[1])
        if m:
            return (int(m.group(1)), int(m.group(2)), m.group(3))


def get_authorized_keys_file(user):
    u = info['posix.users'][user]
    ak_file = config['ssh_authorized_keys_file'].format(
        name=u.name, home=u.home)
    log.debug('Authorized key file for {}: {}'.format(u.name, ak_file))
    return ak_file


AK_DIR_PERMS = 0o700
AK_FILE_PERMS = 0o600
KEY_FILE_PERMS = 0o600


@operation()
def set_authorized_keys(files, user='root', fix_permissions=True):
    ak_file = init_authorized_keys(user, fix_permissions).value

    kf = KeyFile()

    for fn in files:
        kf.add_from_file(fn)

    # directory is guaranteed to exist now, with correct permissions
    upload = fs.upload_string(str(kf), ak_file)

    if upload.changed and fix_permissions:
        fs.chmod(ak_file, AK_FILE_PERMS)
        fs.chown(ak_file, uid=user)

    fps = ', '.join(k.readable_fingerprint for k in kf.keys)

    if upload.changed:
        return Changed(msg='SSH authorized keys for {} set to: {}'.format(
            user, fps))

    return Unchanged(msg='SSH authorized keys for {} unchanged ({})'.format(
        user, fps))


@operation()
def init_authorized_keys(user='root', fix_permissions=True):
    ak_file = get_authorized_keys_file(user)
    ak_dir = remote.path.dirname(ak_file)

    changed = False

    # ensure the directory exists
    changed |= fs.create_dir(ak_dir, mode=AK_DIR_PERMS).changed

    if fix_permissions:
        changed |= fs.chmod(ak_dir, AK_DIR_PERMS).changed
        changed |= fs.chown(ak_dir, uid=user).changed

    # check if the authorized keys file exists
    if not remote.lstat(ak_file):
        changed |= fs.touch(ak_file).changed

    if fix_permissions:
        changed |= fs.chmod(ak_file, AK_FILE_PERMS).changed
        changed |= fs.chown(ak_dir, uid=user).changed

    # at this point, we have fixed permissions for file and dir, as well as
    # ensured they exist. however, they might still be owned by root

    if changed:
        return Changed(
            ak_file, msg='Changed permissions or owner on authorized keys')
    return Unchanged(
        ak_file, msg='authorized keys file has correct owner and permissions')


@operation()
def regenerate_host_keys(mark='/etc/ssh/host_keys_regenerated'):
    if mark:
        if remote.lstat(mark):
            return Unchanged(msg='Hostkeys have already been regenerated')

    key_names = [
        '/etc/ssh/ssh_host_ecdsa_key',
        '/etc/ssh/ssh_host_ed25519_key',
        '/etc/ssh/ssh_host_rsa_key',
        '/etc/ssh/ssh_host_dsa_key',
    ]

    def collect_fingerprints():
        fps = ''
        for key in key_names:
            if remote.lstat(key):
                fps += proc.run(['ssh-keygen', '-l', '-f', key])[0]
        return fps

    old_fps = collect_fingerprints()

    # remove old keys
    for key in key_names:
        fs.remove_file(key)
        fs.remove_file(key + '.pub')

    # generate new ones
    proc.run(['dpkg-reconfigure', 'openssh-server'])

    # restart openssh
    systemd.restart_unit('ssh.service')

    new_fps = collect_fingerprints()

    # mark host keys as new
    fs.touch(mark)

    return Changed(msg='Regenerated SSH host keys.\n'
                   'Old fingerprints:\n{}\nNew fingerprints:\n{}\n'.format(
                       util.indent('    ', old_fps),
                       util.indent('    ', new_fps)))


@operation()
def grant_me_root(my_key='~/.ssh/id_rsa.pub', unlock_root=True):
    c = set_authorized_keys([os.path.expanduser(my_key)], user='root').changed

    if unlock_root:
        # we need to unlock the root user, otherwise a login is not possible
        # via ssh
        c |= posix.set_unlocked_no_password(['root']).changed

    if c:
        return Changed(msg='Granted root ssh login')
    return Unchanged(msg='Already have root login')


@operation()
def install_private_key(key_file,
                        user='root',
                        key_type='rsa',
                        target_path=None):

    if target_path is None:
        # FIXME: auto-determine key type if None
        if key_type not in ('rsa', ):
            raise NotImplementedError('Key type {} not supported')

        fn = 'id_' + key_type
        target_path = remote.path.join(info['posix.users'][user].home, '.ssh',
                                       fn)

    changed = False

    # blocked: SSH transport does not suppoort
    # with remote.umasked(0o777 - KEY_FILE_PERMS):
    changed |= fs.create_dir(
        remote.path.dirname(target_path), mode=AK_DIR_PERMS).changed

    changed |= fs.upload_file(key_file, target_path).changed
    changed |= fs.chmod(target_path, mode=KEY_FILE_PERMS).changed

    if changed:
        return Changed(msg='Installed private key {}'.format(target_path))
    return Unchanged(
        msg='Private key {} already installed'.format(target_path))


@operation()
def install_hostkeys(base_dir):
    results = []

    for key_type in ('ecdsa', 'ed25519', 'rsa'):
        fn = 'ssh_host_' + key_type + '_key'
        pub_fn = fn + '.pub'
        sk = os.path.join(base_dir, fn)
        pk = os.path.join(base_dir, pub_fn)

        results.append(fs.upload_file(sk, '/etc/ssh/' + fn))
        results.append(fs.upload_file(pk, '/etc/ssh/' + pub_fn))

    if util.any_changed(*results):
        systemd.reload_unit('ssh.service')
        return Changed(msg='Installed SSH hostkeys from {}'.format(base_dir))

    return Unchanged(msg='SSH hostkeys already installed')
