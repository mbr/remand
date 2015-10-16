from __future__ import absolute_import

from contextlib import contextmanager
import os
import SocketServer
import select
import threading

import contextlib2
import volatile

from .. import remote, log


@contextmanager
def remote_socket():
    import socket as mod_s
    from . import monkey_socket as monkey_s

    old_attrs = {}

    # save old functions/attributes, then money_patch
    for name in monkey_s.__all__:
        if hasattr(mod_s, name):
            old_attrs[name] = getattr(mod_s, name)
        setattr(mod_s, name, getattr(monkey_s, name))

    yield

    # restore original functions/attributes. remove those added
    for name in monkey_s.__all__:
        if name in old_attrs:
            setattr(mod_s, name, old_attrs[name])
        else:
            delattr(mod_s, name)


@contextmanager
def local_forward(remote_addr, local_addr=('127.0.0.1', 0)):
    class Handler(SocketServer.BaseRequestHandler):
        def handle(self):
            my_log.debug('New connection to {} from {}'.format(
                remote_addr, self.request.getpeername()))

            chan = my_remote.tcp_connect(remote_addr)

            while True:
                r, _, _ = select.select([self.request, chan], [], [])

                if self.request in r:
                    buf = self.request.recv(4096)
                    if len(buf) == 0:
                        # client closed connection, we're done
                        break
                    chan.send(buf)

                if chan in r:
                    buf = chan.recv(4096)
                    if len(buf) == 0:
                        # server closed connection
                        break
                    self.request.send(buf)

            my_log.debug('Closed connection to {} from {}'.format(
                remote_addr, self.request.getpeername()))

    with contextlib2.ExitStack() as stack:
        if isinstance(local_addr, tuple):
            server = SocketServer.ThreadingTCPServer(local_addr, Handler)
        else:
            # assume its a string, denoting a unix domain socket
            if not local_addr:
                dtmp = stack.enter_context(volatile.dir())
                local_addr = os.path.join(dtmp, 'remote.sock')
            server = SocketServer.UnixStreamServer(local_addr, Handler)

        server.allow_reuse_address = False
        server.daemon_threads = True

        my_remote = remote._get_current_object()

        # FIXME: is logging thread-safe?
        my_log = log._get_current_object()

        t = threading.Thread(target=server.serve_forever)
        t.daemon = True
        t.start()

        # wait for the server to shutdown
        stack.callback(t.join)
        stack.callback(server.shutdown)
        stack.callback(
            log.debug,
            'Waiting for shutdown of {}'.format(server.server_address))

        log.debug('Forward established: {} => {}'.format(
            server.server_address, remote_addr))
        yield server.server_address
