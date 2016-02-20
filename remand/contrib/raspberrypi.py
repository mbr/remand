from remand import Plan, operation, Changed, Unchanged
from remand.lib import posix, proc, linux, apt, systemd, fs

rpi = Plan(__name__)


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
        # FIXME: run fdisk and resize2fs instead of raspi-config?
        proc.run(['raspi-config', '--expand-rootfs'])
        return Changed(msg='Expanded root filesystem')


@operation()
def enable_hwrng():
    c = linux.enable_module('bcm2708_rng').changed
    c |= apt.install_packages(['rng-tools']).changed
    c |= systemd.enable_unit('rng-tools.service').changed
    c |= systemd.start_unit('rng-tools.service').changed

    return c


@operation()
def enable_spi():
    # FIXME: instead of rebooting, add a reboot_required property to
    # Changed/Unchanged and allow chaining these.
    #
    # e.g.
    #
    # c = some_operation()
    # c = c.chain(another_operation, msg=....)
    #
    # return c
    #
    # at any point in time, c.reboot_required can be resolved, either
    # in a plan/operation or by the driver ("reboot_if_needed()")

    # FIXME: check for /etc/modprobe.d/raspi-blacklist.conf
    #        mentioned at https://www.raspberrypi.org/documentation/
    #                             hardware/raspberrypi/spi/README.md

    with fs.edit('/boot/config.txt', create=False) as boot:
        boot.insert_line('dtparam=spi=on')
        boot.insert_line('dtoverlay=spi-bcm2835-overlay')

    if boot.changed:
        linux.enable_module('spi_bcm2835', load=False)
        return Changed('Enabled SPI, need to reboot now')

    if linux.enable_module('spi_bcm2835').changed:
        return Changed('SPI kernel module enabled')

    return Unchanged('SPI already enabled')


@rpi.objective()
def init_jessie():
    needs_reboot = False

    # first, expand the filesystem
    needs_reboot |= expand_root_fs().changed

    if needs_reboot:
        posix.reboot()

    # then, initialize the rng
    enable_hwrng()
