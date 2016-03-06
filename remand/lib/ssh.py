import os

from remand import config, info, log, remote
from remand.lib import fs
from remand.operation import operation, Changed, Unchanged

from sshkeys import Key


class KeyFile(object):
    def __init__(self):
        self.keys = []

    def add(self, key):
        self.keys.append(key)

    def add_from_file(self, path):
        self.keys.append(Key.from_pubkey_file(path))

    def __str__(self):
        return ''.join(k.to_pubkey_line() + '\n' for k in self.keys)


def get_authorized_keys_file(user):
    u = info['posix.users'][user]
    ak_file = config['ssh_authorized_keys_file'].format(name=u.name,
                                                        home=u.home)
    log.debug('Authorized key file for {}: {}'.format(u.name, ak_file))
    return ak_file


AK_DIR_PERMS = 0o700
AK_FILE_PERMS = 0o600


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

    fps = ', '.join(k.readable_fingerprint for k in kf.keys)

    if upload.changed:
        return Changed(
            msg='SSH authorized keys for {} set to: {}'.format(user, fps))

    return Unchanged(
        msg='SSH authorized keys for {} unchanged ({})'.format(user, fps))


@operation()
def init_authorized_keys(user='root', fix_permissions=True):
    ak_file = get_authorized_keys_file(user)
    ak_dir = remote.path.dirname(ak_file)

    changed = False

    # ensure the directory exists
    changed |= fs.create_dir(ak_dir, mode=AK_DIR_PERMS).changed

    if fix_permissions:
        changed |= fs.chmod(ak_dir, AK_DIR_PERMS).changed

    # check if the authorized keys file exists
    if not remote.lstat(ak_file):
        changed |= fs.touch(ak_file).changed

    if fix_permissions:
        changed |= fs.chmod(ak_file, AK_FILE_PERMS).changed

    # at this point, we have fixed permissions for file and dir, as well as
    # ensured they exist. however, they might still be owned by root

    if changed:
        return Changed(ak_file,
                       msg='Changed permissions or owner on authorized keys')
    return Unchanged(
        ak_file,
        msg='authorized keys file has correct owner and permissions')


@operation()
def grant_me_root(my_key='~/.ssh/id_rsa.pub'):
    return set_authorized_keys([os.path.expanduser(my_key)], user='root')
