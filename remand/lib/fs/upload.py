from shutil import copyfileobj

from remand import remote
from remand.exc import ConfigurationError
from .util import RegistryBase


class Uploader(RegistryBase):
    registry = {}

    def upload_file(self, local_path, remote_path):
        raise ConfigurationError('{} does not support file uploads.'.format(
            self.__class__.__name__
        ))

    def upload_buffer(self, buf, remote_path):
        raise ConfigurationError('{} does not support buffer uploads.'.format(
            self.__class__.__name__
        ))


@Uploader._registered
class UploaderRsync(Uploader):
    short_name = 'rsync'


@Uploader._registered
class UploaderWrite(Uploader):
    short_name = 'write'

    def upload_file(self, local_path, remote_path):
        with file(local_path, 'rb') as src,\
                remote.file(remote_path, 'wb') as dst:
            copyfileobj(src, dst)
