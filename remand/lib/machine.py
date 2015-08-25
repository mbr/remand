from remand import config
from remand.lib import proc
from remand.operation import operation, Changed


@operation()
def reboot():
    if config['machine_os'] in ('unix', 'posix'):
        proc.run([config['cmd_shutdown'], '-r', 'now'])
    return Changed(msg='Server rebooting')
