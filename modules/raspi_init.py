import os

from remand import remote
from remand.lib import proc, fs, apt, ssh, posix, machine
from remand.operation import operation, Changed, Unchanged

from collections import namedtuple

PUB_KEY = os.path.expanduser('~/.ssh/id_rsa.pub')

UserEntry = namedtuple('UserEntry', 'name,pw,uid,gid,gecos,home,shell')


@operation()
def disable_raspi_config():
    # FIXME: use fs.edit here
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


@operation()
def expand_root_fs():
    dev_size, _, _ = proc.run(['fdisk', '-s', '/dev/mmcblk0'])
    p1_size, _, _ = proc.run(['fdisk', '-s', '/dev/mmcblk0p1'])
    p2_size, _, _ = proc.run(['fdisk', '-s', '/dev/mmcblk0p2'])
    free_space = (int(dev_size) - int(p1_size) - int(p2_size)) * 512

    if free_space <= 4 * 1024 * 1024:
        return Unchanged(
            msg='Free space is <= 4M. Not expanding root filesystem')
    else:
        # fixme: run fdisk and resize2fs instead of raspi-config?
        proc.run(['raspi-config', '--expand-rootfs'])
        return Changed(msg='Expanded root filesystem')


@operation()
def enable_systemd():
    changed = False
    changed |= apt.install_packages(['systemd']).changed

    with fs.edit('/boot/cmdline.txt', create=False) as e:
        flag = 'init=/bin/systemd'
        lines = e.lines()
        assert len(lines) == 1

        if flag not in lines[0]:
            lines[0] += ' ' + flag
            e.set_lines(lines)

    changed |= e.changed

    if changed:
        return Changed(msg='Installed systemd')

    return Unchanged(msg='systemd already active')


def run():
    needs_reboot = False

    with proc.sudo():
        ssh.set_authorized_keys([PUB_KEY], 'root')
        posix.userdel('pi', remove_home=True, force=True)
        disable_raspi_config()

        needs_reboot |= expand_root_fs().changed
        needs_reboot |= enable_systemd().changed

        if needs_reboot:
            machine.reboot()
