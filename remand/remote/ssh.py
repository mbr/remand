from paramiko.client import SSHClient, AutoAddPolicy, RejectPolicy
from paramiko.ssh_exception import SSHException

from remand import config
from remand.exc import TransportError


class SSHRemote(object):
    def __init__(self, hostname, username, port):
        # FIXME: audit this
        self._client = SSHClient()

        if config['ssh'].getboolean('load_system_host_keys'):
            self._client.load_system_host_keys()

        rej_policy = (AutoAddPolicy()
                      if config['ssh'].getboolean('allow_unknown_hosts')
                      else RejectPolicy())
        self._client.set_missing_host_key_policy(rej_policy)

        try:
            self._client.connect(hostname, port or 22, username or 'root')
        except SSHException, e:
            raise TransportError('SSH: {}'.format(e))
