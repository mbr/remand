from .ssh import SSHRemote
from .. import config
from ..uri import Uri


class VagrantRemote(SSHRemote):
    def __init__(self):
        # just override some settings. first, we connect to localhost
        config['uri'] = Uri.from_string('ssh://localhost:2222')
        config['ssh_private_key'] = config['vagrant_private_key']

        return super(VagrantRemote, self).__init__()
