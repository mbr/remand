from functools import partial
import os

from remand import config
from remand.operation import operation, Changed, Unchanged
from remand.lib import fs, proc

UNIT_EXTS = ('.target', '.service', '.socket', '.timer', '.mount')
NETWORK_EXTS = ('.network', '.netdev', '.link')


# FIXME: should be info?
def get_unit_state(unit_name):
    stdout, _, _ = proc.run([config['cmd_systemctl'], 'show', unit_name])
    return dict(line.split('=', 1) for line in stdout.splitlines())


def _ensure_unit(service_name, upload_func, enable, auto_restart):
    # FIXME: we also support sockets!
    # assert service_name.endswith('.service')

    changed = upload_func().changed

    # FIXME: check if restart was successful?
    if auto_restart and changed:
        restart_unit(service_name)

    if enable:
        changed |= enable_unit(service_name).changed

    if changed:
        return Changed(
            msg='Unit {} updated and restarted'.format(service_name))

    return Unchanged(
        msg='Unit {} already up to date and running'.format(service_name))


@operation()
def ensure_unit(unit_file, enable=True, auto_restart=True):
    service_name = os.path.basename(unit_file)
    upload_func = partial(install_unit_file, unit_file, reload=True)
    return _ensure_unit(service_name, upload_func, enable, auto_restart)


@operation()
def ensure_unit_string(service_name, buf, enable=True, auto_restart=True):
    upload_func = partial(install_unit_string, service_name, buf, reload=True)
    return _ensure_unit(service_name, upload_func, enable, auto_restart)


@operation()
def install_unit_string(unit_name, buf, reload=True):
    _, ext = os.path.splitext(unit_name)

    if ext not in UNIT_EXTS:
        raise ValueError('unit_name should be one of {}'.format(UNIT_EXTS))

    remote_unit = os.path.join(config['systemd_unit_dir'],
                               os.path.basename(unit_name))

    if fs.upload_string(buf, remote_unit).changed:
        if reload:
            daemon_reload()
        return Changed(msg='Installed {}'.format(remote_unit))

    return Unchanged(msg='{} already installed'.format(remote_unit))


@operation()
def install_unit_file(unit_file, reload=True):
    base, ext = os.path.splitext(unit_file)

    if ext not in UNIT_EXTS:
        raise ValueError('unit_file should be one of {}'.format(UNIT_EXTS))

    remote_unit = os.path.join(config['systemd_unit_dir'],
                               os.path.basename(unit_file))

    if fs.upload_file(unit_file, remote_unit).changed:
        if reload:
            daemon_reload()
        return Changed(msg='Installed {}'.format(remote_unit))

    return Unchanged(msg='{} already installed'.format(remote_unit))


@operation()
def install_network_file(network_file, reload=True):
    base, ext = os.path.splitext(network_file)

    if ext not in NETWORK_EXTS:
        raise ValueError('network_file should be one of {}'.format(
            NETWORK_EXTS))

    remote_network = os.path.join(config['systemd_network_dir'],
                                  os.path.basename(network_file))

    if fs.upload_file(network_file, remote_network).changed:
        if reload:
            daemon_reload()
        return Changed(msg='Installed {}'.format(remote_network))

    return Unchanged(msg='{} already installed'.format(remote_network))


# FIXME: rethink names, might need a simple "enable" function here
@operation()
def enable_unit(unit_name, check_first=False):
    if check_first:
        state = get_unit_state(unit_name)
        # we use 'WantedBy' as a guess whether or not the service is enabled
        # when UnitFileState is not available (SysV init or older systemd)
        ufs = state.get('UnitFileState')
        if ufs == 'enabled' or ufs is None and 'WantedBy' in state:
            return Unchanged(msg='{} already enabled'.format(unit_name))

    proc.run([config['cmd_systemctl'], 'enable', unit_name])
    return Changed(msg='Enabled {}'.format(unit_name))


@operation()
def disable_unit(unit_name):
    state = get_unit_state(unit_name)
    if state.get('UnitFileState') == 'disabled':
        return Unchanged(msg='{} already disabled'.format(unit_name))

    proc.run([config['cmd_systemctl'], 'disable', unit_name])
    return Changed(msg='Disabled {}'.format(unit_name))


@operation()
def start_unit(unit_name):
    state = get_unit_state(unit_name)
    if 'ActiveState' in state and state['ActiveState'] == 'active' and state[
            'SubState'] == 'running':
        return Unchanged(msg='{} already running'.format(unit_name))

    proc.run([config['cmd_systemctl'], 'start', unit_name])
    return Changed(msg='Started {}'.format(unit_name))


@operation()
def stop_unit(unit_name):
    state = get_unit_state(unit_name)
    if state['ActiveState'] == 'stopped':
        return Unchanged(msg='{} already stopped'.format(unit_name))

    proc.run([config['cmd_systemctl'], 'stop', unit_name])
    return Changed(msg='Stopped {}'.format(unit_name))


@operation()
def restart_unit(unit_name):
    proc.run([config['cmd_systemctl'], 'restart', unit_name])
    return Changed(msg='Restarted {}'.format(unit_name))


@operation()
def daemon_reload():
    proc.run([config['cmd_systemctl'], 'daemon-reload'])
    return Changed(msg='systemd daemon-reload\'ed')
