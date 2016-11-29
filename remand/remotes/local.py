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
        log.debug('Setting umask to {:o}'.format(umask))
        os.umask(umask)

    chdir = os.chdir
    chmod = os.chmod
    file = open
    getcwd = os.getcwd
    listdir = os.listdir

    def lstat(self, path):
        try:
            return os.lstat(path)
        except OSError as e:
            if e.errno != 2:
                raise
            return None
        # Python3:
        # except FileNotFoundError:
        #    return None

    mkdir = os.mkdir
    normalize = lambda path: os.path.abspath(os.path.realpath(path))
    readlink = os.readlink
    rename = lambda oldpath, newpath: os.rename(oldpath, newpath)

    rmdir = os.rmdir

    def stat(self, path):
        try:
            return os.stat(path)
        except OSError as e:
            if e.errno != 2:
                raise
            return None
        # Python3:
        # except FileNotFoundError:
        #    return None

    symlink = os.symlink
    umask = os.umask
    unlink = os.unlink
    utime = os.utime

    def popen(self, args, cwd=None, extra_env={}):
        env = {}
        env.update(os.environ)
        env.update(extra_env)
        proc = subprocess.Popen(args,
                                cwd=cwd,
                                env=env,
                                stdin=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                stdout=subprocess.PIPE)

        orig_communicate = proc.communicate

        # decorate communicate to accept read instances
        def _communicate(input):
            if input and hasattr(input, 'read'):
                # FIXME: this is fairly bad (large files!). needs a
                # modification of the original API or a reimplementation of the
                # communicate method
                input = input.read()
            return orig_communicate(input)

        proc.communicate = _communicate

        return proc

    def tcp_connect(self, addr):
        # cannot log here, must be callable by other threads

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(addr)
        return s

    def file(self, name, mode='r'):
        return open(name, mode)
