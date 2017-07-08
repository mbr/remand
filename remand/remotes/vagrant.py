import os

from ..exc import TransportError
from .ssh import SSHRemote
from .. import config
from ..uri import Uri


class VagrantRemote(SSHRemote):
    def __init__(self):
        # just override some settings. first, we connect to localhost.
        # we use 127.0.0.1, because on some machines, "localhost" may resolve
        # to ::1 first
        config['uri'] = Uri.from_string('ssh://vagrant@127.0.0.1:2222')

        key = config['vagrant_secret_key']

        if not os.path.isfile(key):
            raise TransportError(
                'Could not find the Vagrant SSH private key at {}. Please '
                'ensure the file exists and is readable or configure the '
                '`vagrant_secret_key` setting.'.format(key))


        config['ssh_private_key'] = config['vagrant_secret_key']
        config['on_missing_host_key'] = 'ignore'

        return super(VagrantRemote, self).__init__()
