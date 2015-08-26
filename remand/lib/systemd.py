import os

from remand import config
from remand.operation import operation, Changed, Unchanged
from remand.lib import fs, proc

UNIT_EXTS = ('.target', '.service', '.socket')


# FIXME: should be info?
def get_unit_state(unit_name):
    stdout, _, _ = proc.run([config['cmd_systemctl'], 'show', unit_name])
    return dict(line.split('=', 1) for line in stdout.splitlines())


@operation()
def install_unit_file(unit_file, reload=True):
    base, ext = os.path.splitext(unit_file)

    if ext not in UNIT_EXTS:
        raise ValueError('unit_file should be one of {}'.format(UNIT_EXTS))

    remote_unit = os.path.join(config['systemd_unit_dir'],
                               os.path.basename(unit_file))

    if fs.upload_file('gogs.service', remote_unit).changed:
        if reload:
            daemon_reload()
        return Changed(msg='Installed {}'.format(remote_unit))

    return Unchanged(msg='{} already installed'.format(remote_unit))


@operation()
def enable_unit(unit_name):
    state = get_unit_state(unit_name)
    if state['UnitFileState'] == 'enabled':
        return Unchanged(msg='{} already enabled'.format(unit_name))

    proc.run([config['cmd_systemctl'], 'enable', unit_name])
    return Changed(msg='Enabled {}'.format(unit_name))


@operation()
def start_unit(unit_name):
    state = get_unit_state(unit_name)
    if state['ActiveState'] == 'started':
        return Unchanged(msg='{} already started'.format(unit_name))

    proc.run([config['cmd_systemctl'], 'start', unit_name])
    return Changed(msg='Started {}'.format(unit_name))


@operation()
def daemon_reload():
    proc.run([config['cmd_systemctl'], 'daemon-reload'])
    return Changed(msg='systemd daemon-reload\'ed')
