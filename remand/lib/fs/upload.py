from shutil import copyfileobj

from remand import remote
from .util import RegistryBase


class Uploader(RegistryBase):
    registry = {}

    def upload_file(self, local_path, remote_path):
        raise NotImplementedError

    def upload_buffer(self, buf, remote_path):
        raise NotImplementedError


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
