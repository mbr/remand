import os

from remand import operation, Changed, Unchanged, remote, config
from remand.lib import fs
from remand.exc import ConfigurationError


@operation()
def install_cert(cert, key, cert_name=None, key_name=None):
    cert_name = cert_name or os.path.basename(cert)
    key_name = key_name or os.path.basename(key)

    # small sanity check
    with open(cert) as f:
        if 'PRIVATE' in f.read():
            raise ValueError(
                'You seem to have passed a private key as a cert!')

    with open(key) as f:
        if 'PRIVATE' not in f.read():
            raise ValueError(
                '{} does not seem to be a valid private key'.format(key))

    # check if remote is reasonably secure
    cert_dir = config['sslcert_cert_dir']
    cert_dir_st = remote.lstat(cert_dir)

    if not cert_dir_st:
        raise ConfigurationError('Remote SSL dir {} does not exist'.format(
            cert_dir))

    key_dir = config['sslcert_key_dir']
    key_dir_st = remote.lstat(key_dir)

    if not key_dir_st:
        raise ConfigurationError('Remote key dir {} does not exist'.format(
            key_dir))

    SECURE_MODES = (0o700, 0o710)
    actual_mode = key_dir_st.st_mode & 0o777
    if actual_mode not in SECURE_MODES:
        raise ConfigurationError(
            'Mode of remote key dir {} is {:o}, should be one of {:o}'.format(
                key_dir, actual_mode, SECURE_MODES))

    if key_dir_st.st_uid != 0:
        raise ConfigurationError(
            'Remove key dir {} is not owned by root'.format(key_dir))

    # we can safely upload the key and cert
    cert_rpath = remote.path.join(cert_dir, cert_name)
    key_rpath = remote.path.join(key_dir, key_name)

    changed = False
    changed |= fs.upload_file(cert, cert_rpath).changed
    changed |= fs.upload_file(key, key_rpath).changed
    changed |= fs.chmod(key_rpath, 0o600).changed

    if changed:
        return Changed(
            msg='Uploaded key pair {}/{}'.format(cert_name, key_name))

    return Unchanged(
        msg='Key pair {}/{} already uploaded'.format(cert_name, key_name))
