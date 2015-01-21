from shutil import copyfileobj

from remand import remote
from .util import RegistryBase


class Uploader(RegistryBase):
    def upload(self, st, local_path, remote_path):
        raise NotImplementedError


@Uploader._registered
class UploaderRsync(RegistryBase):
    short_name = 'rsync'


@Uploader._registered
class UploaderWrite(RegistryBase):
    short_name = 'write'

    def upload(self, local_path, remote_path):
        with file(local_path, 'rb') as src,\
                remote.file(remote_path, 'wb') as dst:
            copyfileobj(src, dst)
