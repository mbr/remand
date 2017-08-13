import os

from remand.lib import systemd

from remand import Plan, operation, Changed, Unchanged

debian = Plan(__name__, os.path.dirname(__file__))


@operation()
def enable_auto_upgrades(boot_time='10min', unit_active_time='1d', start=True):
    timer_tpl = debian.templates.render(
        'autoupdate.timer',
        boot_time=boot_time,
        unit_active_time=unit_active_time)

    c = False
    # install both timer and service
    c |= systemd.install_unit_string('autoupdate.timer', timer_tpl).changed
    c |= systemd.install_unit_file(debian.files['autoupdate.service']).changed

    # enable both timer and service
    c |= systemd.enable_unit('autoupdate.timer').changed
    c |= systemd.enable_unit('autoupdate.service').changed

    # start timer
    if start:
        c |= systemd.start_unit('autoupdate.timer').changed

    if c:
        return Changed(msg='Enabled automatic apt-updates via systemd timer')
    return Unchanged(
        msg='Automatic apt-updates via systemd timer already enabled')
