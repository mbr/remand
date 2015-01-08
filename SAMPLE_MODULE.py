# this a script that sets up my raspberry pi server

from remand import remote, local
from remand_fs import unlink
from remand_text import add_line_to_file
from remand_users import create_user, drop_user
from remand_reboot import require_reboot, reboot_if_required
from remand_apt import install


def run():
    if remote.upload_file(local.resource('config.txt'), mode=0755):
        schedule_reboot()

    create_user('root', pw='xyz')
    drop_user('pi')
    unlink('/etc/profile.d/raspi-config.sh')

    # simple:
    file_add_lines('/etc/modules', 'bcm2708_rng')

    # better:
    enable_kernel_module('bcm2708_rng')

    # install module
    install('rng-tools')

    # better:
    apt.require('rng-tools')
    if file_add_lines('/etc/default/rng-tools', "HRNGDEVICE=/dev/hwrng"):
        queue_restart('rng-tools')



    # alternative:
    from remand.ext import fs, text, users, reboot, apt, modules

    # outside of source, use names like remand_fs. implementation should support
    # sys.meta_path to add a loader that tries importing these

    # alt 2 (at the start, replace with mechanism above later on?):
    # from remand_fs import fs
    # from remand_text import text
    # from remand_users import users
    # from remand_reboot import reboot
    # from remand_apt import apt

    if remote.upload_file(local.resource('config.txt'), mode=0755):
        reboot.schedule()

    users.create('root', pw='xyz')
    users.drop('pi')
    fs.remove('/etc/profile.d/raspi-config.sh')
    text.add_line('/etc/modules', 'bcm2708_rng')
    modules.enable_modules('bcm2708_rng')
    apt.require('rng-tools')

    if file_add_lines('/etc/default/rng-tools', "HRNGDEVICE=/dev/hwrng"):
        queue_restart('rng-tools')



    # important: nesting. ex: run the secure-ssh script before

    # alt1 (uses plugin-base import magic, would make it possible to install
    #       scripts to pypi):
    from remand.scripts import secure_ssh

    # keeps namespace reasonably clean, has few surprises
    # other alternatives seem too hackish
