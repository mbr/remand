from paramiko.client import SSHClient, AutoAddPolicy, RejectPolicy
from paramiko.ssh_exception import SSHException

from remand import config
from remand.exc import TransportError

_KNOWN_HOSTS_ERROR = ("The host '{}' was not found in your known_hosts file. "
"Remand is refusing to connect to unknown hosts.\n\n"
"If you have an older version of Paramiko installed, this may be because of "
"a key-type mismatch.\n\n")


class SSHRemote(object):
    def __init__(self, hostname, username, port):
        # FIXME: audit this
        self._client = SSHClient()

        if config['ssh'].getboolean('load_known_hosts'):
            self._client.load_system_host_keys()

        rej_policy = (AutoAddPolicy()
                      if config['ssh'].getboolean('allow_unknown_hosts')
                      else RejectPolicy())
        self._client.set_missing_host_key_policy(rej_policy)

        try:
            self._client.connect(hostname, port or 22, username or 'root')
        except SSHException, e:
            if 'not found in known_hosts' in e.message:
                raise TransportError(_KNOWN_HOSTS_ERROR.format(hostname))
            raise TransportError('SSH: {}'.format(e))
