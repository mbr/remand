from binascii import hexlify
from functools import wraps

from paramiko.client import SSHClient, AutoAddPolicy, RejectPolicy
from paramiko.ssh_exception import SSHException, BadHostKeyException

from . import Remote
from .. import config, log
from ..exc import TransportError

_KNOWN_HOSTS_ERROR = (
    "The host '{}' was not found in your known_hosts file. "
    "Remand is refusing to connect to unknown hosts.\n\n"
    "If you have an older version of Paramiko installed, this may be because "
    "of a key-type mismatch.\n\n"
    "See https://github.com/paramiko/paramiko/pull/473 for more information.")


_BAD_KEY_ERROR = (
    "The remote host's key does not match the key in your known_hosts file.\n"
    # for extra drama, we copy the openssh error message
    "IT IS POSSIBLE THAT SOMEONE IS DOING SOMETHING NASTY!\n\n"
    "Remote host key: {} {}\n"
    "known_hosts key: {} {}\n\n"
    "The host key for {} has changed and checking is enabled."
)


def format_key(key):
    return ':'.join(hexlify(b) for b in key.get_fingerprint())


def ssh_host_name(uri):
    if uri.port is None or uri.port == 22:
        return uri.host
    else:
        return '[{0.host}]:{0.port}'.format(uri)


def wrap_ssh_errors(f):
    @wraps(f)
    def _(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except SSHException, e:
            raise TransportError('SSH ({}): {}'.format(
                type(e).__name__, e.message))
    return _


class SSHRemote(Remote):
    uri_prefix = 'ssh'

    __sftp = None

    @wrap_ssh_errors
    def __init__(self):
        self._client = SSHClient()

        if config.get_bool('load_known_hosts', True):
            self._client.load_system_host_keys()

        rej_policy = (AutoAddPolicy()
                      if config.get_bool('disable_host_key_checking', False)
                      else RejectPolicy())
        self._client.set_missing_host_key_policy(rej_policy)

        uri = config['uri']
        try:
            self._client.connect(uri.host, uri.port or 22, uri.user)
        except BadHostKeyException, e:
            raise TransportError(_BAD_KEY_ERROR.format(
                e.key.get_name(),
                format_key(e.key),
                e.expected_key.get_name(),
                format_key(e.expected_key),
                ssh_host_name(uri),
            ))
        except SSHException, e:
            if 'not found in known_hosts' in e.message:
                raise TransportError(_KNOWN_HOSTS_ERROR.format(uri.host))
            raise

        log.info('SSH connection complete')

    @property
    def _sftp(self):
        if not self.__sftp:
            self.__sftp = self._client.open_sftp()
        return self.__sftp

    @wrap_ssh_errors
    def getcwd(self):
        return self._sftp.normalize('.')
