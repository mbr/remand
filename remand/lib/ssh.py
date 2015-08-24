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


@operation()
def set_authorized_keys(files, user='root', fix_permissions=True):
    DIR_PERMS = 0o700
    FILE_PERMS = 0o600

    kf = KeyFile()

    for fn in files:
        kf.add_from_file(fn)

    u = info['posix.users'][user]
    ak_file = config['ssh_authorized_keys_file'].format(name=u.name,
                                                        home=u.home)
    log.debug('Authorized key file for {}: {}'.format(u.name, ak_file))

    ak_dir = remote.path.dirname(ak_file)

    dir_creation = fs.create_dir(ak_dir, mode=0o700)

    if dir_creation.changed and fix_permissions:
        fs.chmod(ak_dir, DIR_PERMS)

    # directory is guaranteed to exist now
    # FIXME: there's a race condition here, upload_file should support setting
    #        the file mode
    upload = fs.upload_string(str(kf), ak_file)

    if upload.changed or fix_permissions:
        fs.chmod(ak_file, FILE_PERMS)

    fps = ', '.join(k.readable_fingerprint for k in kf.keys)
    if upload.changed:
        return Changed(
            msg='SSH authorized keys for {} set to: {}'.format(user, fps))

    return Unchanged(
        msg='SSH authorized keys for {} unchanged ({})'.format(user, fps))
