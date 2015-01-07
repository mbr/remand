from six.moves import shlex_quote

from paramiko import SSHClient
from paramiko.client import AutoAddPolicy, RejectPolicy


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


class SSHError(Exception):
    pass


class ParasiteConnection(object):
    _sftp = None
    _ssh = None

    @property
    def sftp(self):
        if not self._sftp:
            self._sftp = self.ssh.open_sftp()
        return self._sftp

    @property
    def ssh(self):
        if not self._ssh:
            raise SSHError('Not connected')
        return self._ssh

    def __init__(self,
                 load_system_host_keys=True,
                 auto_add_host_keys=False,
                 cmd_timeout=2):
        self.cmd_timeout = cmd_timeout
        self.load_system_host_keys = load_system_host_keys
        self.auto_add_host_keys = auto_add_host_keys

    def connect(self, *args, **kwargs):
        ssh = SSHClient()
        if self.load_system_host_keys:
            ssh.load_system_host_keys()
        rej_policy = (AutoAddPolicy() if self.auto_add_host_keys else
                      RejectPolicy())
        ssh.set_missing_host_key_policy(rej_policy)

        ssh.connect(*args, **kwargs)
        self._ssh = ssh

    def exec_command(self, cmd, *args, **kwargs):
        if isinstance(cmd, list):
            cmd = ' '.join(shlex_quote(part) for part in cmd)
        return self.ssh.exec_command(cmd)

    def run_command(self, args, input=None, timeout=None):
        timeout = timeout or self.cmd_timeout

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
