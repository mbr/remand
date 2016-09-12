from remand import operation, Changed, remote, config
from remand.lib import proc


def start(service):
    raise NotImplementedError


def stop(service):
    raise NotImplementedError


@operation()
def restart(service):
    proc.run([remote.path.join(config['sysv_initd'], service), 'restart'])
    return Changed(msg='Restarted {}'.format(service))
