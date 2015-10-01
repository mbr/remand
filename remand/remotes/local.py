import os
import socket
import subprocess

from .base import Remote
from .. import config, log


class LocalRemote(Remote):
    uri_prefix = 'local'

    def __init__(self):
        # verify umask
        umask = int(config['reset_umask'], 8)
        log.debug('Setting umask to {}'.format(umask))
        os.umask(umask)

    chdir = os.chdir
    chmod = os.chmod
    file = open
    getcwd = os.getcwd
    listdir = os.listdir
    lstat = os.lstat
    mkdir = os.mkdir
    normalize = lambda path: os.path.abspath(os.path.realpath(path))
    readlink = os.readlink
    rename = lambda oldpath, newpath: os.rename(oldpath, newpath)

    rmdir = os.rmdir
    stat = os.stat
    symlink = os.symlink
    umask = os.umask
    unlink = os.unlink
    utime = os.utime

    def popen(self, args, cwd=None, extra_env={}):
        env = {}
        env.update(os.environ)
        env.update(extra_env)
        return subprocess.Popen(args, cwd=cwd, env=env)

    def tcp_connect(self, addr):
        # cannot log here, must be callable by other threads

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(addr)
        return s

    def file(self, name, mode='r'):
        return open(name, mode)
