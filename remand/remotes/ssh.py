from functools import wraps

from paramiko.client import SSHClient, AutoAddPolicy, RejectPolicy
from paramiko.ssh_exception import SSHException

from . import Remote
from .. import config, log
from ..exc import TransportError

_KNOWN_HOSTS_ERROR = (
    "The host '{}' was not found in your known_hosts file. "
    "Remand is refusing to connect to unknown hosts.\n\n"
    "If you have an older version of Paramiko installed, this may be because "
    "of a key-type mismatch.\n\n")


def wrap_ssh_errors(f):
    @wraps(f)
    def _(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except SSHException, e:
            raise TransportError('SSH: {}'.format(e))
    return _


class SSHRemote(Remote):
    uri_prefix = 'ssh'

    __sftp = None

    def __init__(self, hostname, username, port):
        self._client = SSHClient()

        if config['ssh'].getboolean('load_known_hosts'):
            self._client.load_system_host_keys()

        rej_policy = (AutoAddPolicy()
                      if config['ssh'].getboolean('disable_host_key_checking')
                      else RejectPolicy())
        self._client.set_missing_host_key_policy(rej_policy)

        try:
            self._client.connect(hostname, port or 22, username or 'root')
        except SSHException, e:
            if 'not found in known_hosts' in e.message:
                raise TransportError(_KNOWN_HOSTS_ERROR.format(hostname))
            raise TransportError('SSH: {}'.format(e))

        log.info('SSH connection complete')

    @property
    def _sftp(self):
        if not self.__sftp:
            self.__sftp = self._client.open_sftp()
        return self.__sftp

    @wrap_ssh_errors
    def getcwd(self):
        return self._sftp.normalize('.')
