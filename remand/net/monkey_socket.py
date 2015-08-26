from __future__ import absolute_import

import socket as orig_socket

from .. import log, remote

__all__ = ['socket']


def ignore_method(name, rval=None):
    def _(*args, **kwargs):
        log.debug('Ignored call: {}({}, {})'.format(name, args, kwargs))
        return rval

    return _


class SocketProxy(object):
    def __init__(self,
                 family=orig_socket.AF_INET,
                 type=orig_socket.SOCK_STREAM,
                 proto=0):
        if family not in (orig_socket.AF_INET, orig_socket.AF_INET6):
            raise NotImplementedError('Only TCP supported')
        if type != orig_socket.SOCK_STREAM:
            raise NotImplementedError('Only streaming sockets suppored')
        if proto not in (0, 6):
            raise NotImplementedError(
                'proto parameter {} not supported'.format(proto))

        self._con = None

    def __getattr__(self, name):
        if self._con is not None and hasattr(self._con, name):
            return getattr(self._con, name)

        raise NotImplementedError(
            'SocketProxy does not support socket.{}'.format(name))

    def connect(self, addr):
        self._con = remote.tcp_open(addr)

    def close(self):
        self._con.close()
        self._con = None

    setsockopt = ignore_method('setsockopt')
    settimeout = ignore_method('settimeout')
    gettimeout = ignore_method('gettimeout')


socket = SocketProxy
