import os

from remand import log, remote
from remand.lib import proc, fs
from remand.status import changed, unchanged

PUB_KEY = os.path.expanduser('~/.ssh/id_rsa.pub')

from collections import namedtuple

UserEntry = namedtuple('UserEntry', 'name,pw,uid,gid,gecos,home,shell')


def disable_raspi_config():
    c = False

    # we need to remove it from profile.d
    c |= fs.remove_file('/etc/profile.d/raspi-config.sh')

    # FIXME: this should become part of an edit module?
    lines = []
    inittab_changed = False
    for line in remote.file('/etc/inittab', 'r'):
        if line.startswith('#') and 'RPICFG_TO_ENABLE' in line:
            inittab_changed = True
            lines.append(line[1:line.rfind('#')].strip() + '\n')
            continue

        if 'RPICFG_TO_DISABLE' in line:
            inittab_changed = True
            continue

        lines.append(line)

    if inittab_changed:
        # FIXME: DO THIS ATOMICALLY? Use UPLOAD?
        with remote.file('/etc/inittab', 'w') as out:
            out.write(''.join(lines))
        c = True

    # now just stop running raspi-config
    _, _, status = proc.run(['killall', 'raspi-config'], status_ok=(0, 1))

    # killall will return exit status 1 if not process was found
    if status != 1:
        c = True

    if c:
        changed('Disabled raspi-config')
        return True
    else:
        unchanged('raspi-config already stopped and disabled')
        return False


def register_public_key():
    # FIXME: this should be in a dedicate ssh authorized_keys module
    c = False

    if remote.stat('/home/pi'):
        c |= fs.create_dir('/home/pi/.ssh')
        c |= fs.upload_file(PUB_KEY, '/home/pi/.ssh/authorized_keys')
        changed('Registered ssh key on root')

    with proc.sudo():
        c |= fs.create_dir('/root/.ssh')
        c |= fs.upload_file(PUB_KEY, '/root/.ssh/authorized_keys')
        changed('Registered ssh key on root')

    if c:
        return True
    else:
        unchanged('SSH already setup correctly')
        return False


def expand_root_fs():
    dev_size, _, _ = proc.run(['fdisk', '-s', '/dev/mmcblk0'])
    p1_size, _, _ = proc.run(['fdisk', '-s', '/dev/mmcblk0p1'])
    p2_size, _, _ = proc.run(['fdisk', '-s', '/dev/mmcblk0p2'])
    free_space = (int(dev_size) - int(p1_size) - int(p2_size)) * 512

    if free_space <= 4 * 1024 * 1024:
        unchanged('Free space is <= 4M. Not expanding root filesystem')
        return False
    else:
        changed('Expanded root filesystem')
        proc.run(['raspi-config', '--expand-rootfs'])
    return True


def reboot():
    log.notice('Rebooting')
    proc.run(['reboot'])


def deluser(name, remove_home=True):
    # AGAIN, NEEDS EDIT FUNCTIONS.
    # concept: use a context manager with an edit object. perform edits
    # once it exits, uploading using fs.upload_string
    lines = []
    c = False
    for line in remote.file('/etc/passwd', 'r'):
        u = UserEntry(*line.split(':'))

        if u.name == name:
            c = True
            if remove_home:
                fs.remove_dir(u.home)
            continue

        lines.append(line)

    if c:
        fs.upload_string(''.join(lines), '/etc/passwd')
        changed('Removed user pi')
        return True
    else:
        unchanged('User pi already gone')
        return False


def run():
    register_public_key()
    with proc.sudo():
        deluser('pi')
        disable_raspi_config()

        if expand_root_fs():
            reboot()
