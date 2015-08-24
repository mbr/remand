import os

from remand import log, remote
from remand.lib import proc, fs, apt, ssh
from remand.operation import Changed, Unchanged

from collections import namedtuple

PUB_KEY = os.path.expanduser('~/.ssh/id_rsa.pub')

UserEntry = namedtuple('UserEntry', 'name,pw,uid,gid,gecos,home,shell')


def disable_raspi_config():
    c = False

    # we need to remove it from profile.d
    c |= fs.remove_file('/etc/profile.d/raspi-config.sh').changed

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
        return Changed(msg='Disabled raspi-config')
    else:
        return Unchanged(msg='raspi-config already stopped and disabled')


def expand_root_fs():
    dev_size, _, _ = proc.run(['fdisk', '-s', '/dev/mmcblk0'])
    p1_size, _, _ = proc.run(['fdisk', '-s', '/dev/mmcblk0p1'])
    p2_size, _, _ = proc.run(['fdisk', '-s', '/dev/mmcblk0p2'])
    free_space = (int(dev_size) - int(p1_size) - int(p2_size)) * 512

    if free_space <= 4 * 1024 * 1024:
        return Unchanged(
            msg='Free space is <= 4M. Not expanding root filesystem')
    else:
        proc.run(['raspi-config', '--expand-rootfs'])
        return Changed(msg='Expanded root filesystem')


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
        return Changed(msg='Removed user pi')
    else:
        return Unchanged(msg='User pi already gone')


def run():
    ssh.set_authorized_keys([PUB_KEY], 'pi')
    with proc.sudo():
        ssh.set_authorized_keys([PUB_KEY], 'root')
        deluser('pi')
        disable_raspi_config()

        sd = apt.install_packages(['systemd'])
        # FIXME: currently, need to manually edit /boot/cmdline.txt to add
        #        init=/bin/systemd. this needs edit functions as well
        # also, check for systemd as proc 1 using /proc/1/cmdline or similar

        expand = expand_root_fs()

        if sd.changed or expand.changed:
            reboot()
