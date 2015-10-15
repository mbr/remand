from .ssh import SSHRemote
from .. import config
from ..uri import Uri


class VagrantRemote(SSHRemote):
    def __init__(self):
        # just override some settings. first, we connect to localhost.
        # we use 127.0.0.1, because on some machines, "localhost" may resolve
        # to ::1 first
        config['uri'] = Uri.from_string('ssh://vagrant@127.0.0.1:2222')
        config['ssh_private_key'] = config['vagrant_secret_key']
        config['on_missing_host_key'] = 'ignore'
        config['use_sudo'] = 'on'

        return super(VagrantRemote, self).__init__()
