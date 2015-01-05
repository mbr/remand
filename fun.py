from paramiko import SSHClient

PARASITE = """
#!/usr/bin/python

from struct import unpack, calcsize
from sys import stdin, stdout

HEADER_FMT = '!Q'
HEADER_SIZE = calcsize(HEADER_FMT)

PICKLE_PROTOCOL = 2

while True:
    len = unpack(HEADER_FMT, stdin.read(HEADER_SIZE)
    data = stdin.read(len)

    # error checking....

    reply = {
        'type': 'echo',
        'payload': data,
    }

    stdout.write(pickle.dumps(reply, PICKLE_PROTOCOL))
"""


class CommandResult(object):
    def __init__(self, args=[], exit_status=None, stdout=None, stderr=None):
        self.stdout = stdout
        self.stderr = stderr
        self.exit_status = exit_status
        self.args = args

    def raise_for_status(self, valid_status=[0]):
        if self.exit_status not in valid_status:
            raise RuntimeError('Command {} returned exit status {}'.format(
                self.args, self.exit_status,
            ))


class ParasiteConnection(object):
    @classmethod
    def connect(cls, *args, **kwargs):
        client = SSHClient()
        client.load_system_host_keys()
        client.connect(*args, **kwargs)
        return cls(client)

    def __init__(self, client, timeout=2):
        self.client = client
        self.timeout = timeout

        r = self.run_command(['mktemp'])
        r.raise_for_status()
        remote_fn = r.stdout.strip()

        r = self.run_command(['tee', 'remote_fn'], input=PARASITE)
        r.raise_for_status()
        import pdb
        pdb.set_trace()

    def run_command(self, args, input=None, timeout=None):
        timeout = timeout or self.timeout

        # build command
        command = ' '.join(args)  # FIXME

        # get a new channel
        transport = self.client.get_transport()
        chan = transport.open_session()
        chan.settimeout(timeout)
        chan.exec_command(command)

        stdin = chan.makefile('wb',)
        stdout = chan.makefile('r')
        stderr = chan.makefile_stderr('r')

        # FIXME: this does not work for large inputs (buffer!)
        if input:
            print 'writing...'
            stdin.write(input)
            print 'done writing!'
            stdin.close()
        else:
            stdin.close()

        print 'started', args
        import pdb
        pdb.set_trace()
        exit_status = chan.recv_exit_status()

        print 'done'
        return CommandResult(
            args=args,
            stdout=stdout.read(),
            stderr=stderr.read(),
            exit_status=exit_status,
        )



p = ParasiteConnection.connect('gitpi',
                               username='pi',
                               password='raspberry')
