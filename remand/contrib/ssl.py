import os

import subprocess

from remand import operation, Changed, Unchanged, remote, config, log
from remand.lib import fs
from remand.exc import ConfigurationError
import volatile


def generate_self_signed_cert(hostname):
    # FIXME: instead of openssl, use cryptography/nacl?
    with volatile.dir() as tmp:
        log.info('Generating new temporary self-signed certificate')
        subprocess.check_output(
            [
                'openssl', 'req', '-x509', '-subj', '/CN=' + hostname,
                '-nodes', '-newkey', 'rsa:4096', '-keyout', 'snakeoil.pem',
                '-out', 'snakeoil.crt', '-days', '7'
            ],
            cwd=tmp,
            stderr=subprocess.STDOUT)

        cert = open(os.path.join(tmp, 'snakeoil.crt')).read()
        key = open(os.path.join(tmp, 'snakeoil.pem')).read()

    return key, cert


@operation()
def ensure_certificate(hostname):
    # FIXME: use `ssl.install_cert` here?
    cert_rpath = remote.path.join(config['sslcert_cert_dir'],
                                  hostname + '.crt')
    chain_rpath = remote.path.join(config['sslcert_cert_dir'],
                                   hostname + '.chain.crt')
    key_rpath = remote.path.join(config['sslcert_key_dir'], hostname + '.pem')

    # first, ensure any certificate exists on the host. otherwise,
    # webservers like nginx will likely not start
    if not (remote.lstat(cert_rpath) and remote.lstat(key_rpath)
            and remote.lstat(chain_rpath)):
        log.debug('Remote certificate {}, key {}, chain {} not found'.format(
            cert_rpath, key_rpath, chain_rpath))

        key, cert = generate_self_signed_cert(hostname)

        fs.upload_string(key, key_rpath)
        fs.upload_string(cert, cert_rpath)
        fs.upload_string(cert, chain_rpath)

        return Changed(
            msg='No certificate {} / key {} / chain {} found. A self-signed '
            'certficate from a reputable snake-oil vendor was installed.'.
            format(cert_rpath, key_rpath, chain_rpath))

    return Unchanged(
        'Certificate for hostname {} already preset'.format(hostname))


@operation()
def install_cert(cert, key, cert_name=None, key_name=None):
    """Installs an SSL certificate with including key on the remote

    Certificate filenames are unchanged, per default they will be installed in
    `/etc/ssl`, with the corresponding keys at `/etc/ssl/private`."""
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
        raise ConfigurationError(
            'Remote SSL dir {} does not exist'.format(cert_dir))

    key_dir = config['sslcert_key_dir']
    key_dir_st = remote.lstat(key_dir)

    if not key_dir_st:
        raise ConfigurationError(
            'Remote key dir {} does not exist'.format(key_dir))

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
    changed |= fs.chmod(key_rpath, 0o640).changed
    changed |= fs.chown(key_rpath, uid='root', gid='ssl-cert').changed

    if changed:
        return Changed(msg='Uploaded key pair {}/{}'.format(
            cert_name, key_name))

    return Unchanged(msg='Key pair {}/{} already uploaded'.format(
        cert_name, key_name))
