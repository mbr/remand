from collections import namedtuple, OrderedDict
from crypt import crypt
import hashlib
import os

from remand import config, remote
from remand.exc import RemoteFailureError, ConfigurationError
from remand.lib import proc, memoize, fs
from remand.operation import operation, Unchanged, Changed

_USERADD_STATUS_CODES = {
    0: 'success',
    1: 'can\'t update password file',
    2: 'invalid command syntax',
    3: 'invalid argument to option',
    4: 'UID already in use (and no -o)',
    6: 'specified group doesn\'t exist',
    9: 'username already in use',
    10: 'can\'t update group file',
    12: 'can\'t create home directory',
    13: 'can\'t create mail spool',
    14: 'can\'t update SELinux user mapping',
}

_USERDEL_STATUS_CODES = {
    0: 'success',
    1: 'can\'t update password file',
    2: 'invalid command syntax',
    6: 'specified user doesn\'t exist',
    8: 'user currently logged in',
    10: 'can\'t update group file',
    12: 'can\'t remove home directory',
}

PasswdEntry = namedtuple('PasswdEntry', 'name,passwd,uid,gid,gecos,home,shell')
GroupEntry = namedtuple('GroupEntry', 'name,passwd,gid,user_list')


@memoize()
def info_users():
    users = OrderedDict()

    for line in remote.file('/etc/passwd', 'r'):
        u = PasswdEntry(*line.split(':'))
        users[u.name] = PasswdEntry(u[0], u[1],
                                    int(u[2]), int(u[3]), u[4], u[5], u[6])

    return users


@memoize()
def info_groups():
    groups = OrderedDict()

    for line in remote.file('/etc/group', 'r'):
        g = GroupEntry(*line.split(':'))
        user_list = [u for u in g[3].split(',') if u]
        groups[g.name] = GroupEntry(g[0], g[1], int(g[2]), user_list)

    return groups


@memoize()
def info_system():
    FLAG_LIST = {
        'machine': '-m',
        'nodename': '-n',
        'kernel_name': '-s',
        'kernel_release': '-r',
        'kernel_version': '-v',
        'processor': '-p',
    }

    flag_values = {}
    for flag_name, flag in FLAG_LIST.items():
        out, _, _ = proc.run([config['cmd_uname'], flag])
        flag_values[flag_name] = out.rstrip()

    return flag_values


@memoize()
def info_fqdn():
    res, _, _ = proc.run(['hostname', '--fqdn'])
    return res.strip()


@memoize()
def info_hostname():
    res, _, _ = proc.run(['hostname'])
    return res.strip()


@operation()
def set_hostname(hostname, domain=None, config_only=False):
    prev_hostname = info_hostname()

    changed = False
    changed |= fs.upload_string('{}\n'.format(hostname),
                                '/etc/hostname').changed

    if not config_only and prev_hostname != hostname:
        proc.run(['hostname', hostname])
        changed = True

    # update /etc/hosts
    # this will also set the domain name
    # see http://jblevins.org/log/hostname
    #
    # we adopt the following convention:

    host_line = '127.0.1.1\t' + hostname
    if domain:
        host_line = '127.0.1.1\t{}.{}\t{}'.format(hostname, domain, hostname)

    with fs.edit('/etc/hosts') as hosts:
        if host_line not in hosts.lines():
            hosts.comment_out(r'^127.0.1.1')

            # comment out old lines
            lines = [host_line] + hosts.lines()
            hosts.set_lines(lines)

    changed |= hosts.changed

    if changed:
        info_hostname.invalidate_cache()
        info_fqdn.invalidate_cache()
        return Changed(msg='Hostname changed from {} to {}'.format(
            prev_hostname, hostname))

    return Unchanged(msg='Hostname already set to {}'.format(hostname))


@operation()
def reboot():
    if config.get_bool('systemd'):
        try:
            proc.run([config['cmd_systemctl'], 'reboot'])
        except RemoteFailureError:
            # FIXME: should be more discerning; also verify reboot is taking
            #        place
            pass  # ignored, as the command will not finish - due to rebooting
    elif config['remote_os'] in ('unix', 'posix'):
        proc.run([config['cmd_shutdown'], '-r', 'now'])
    return Changed(msg='Server rebooting')


@operation()
def useradd(name,
            groups=[],
            user_group=True,
            comment=None,
            home=None,
            create_home=None,
            system=False,
            shell=None):
    cmd = [config['cmd_useradd']]

    gs = groups[:]

    if gs:
        if not user_group:
            cmd.extend(('-g', gs.pop(0)))

    if gs:
        cmd.extend(('-G', ','.join(groups)))

    if user_group is True:
        cmd.append('-U')
    elif user_group is False:
        cmd.append('-N')

    if comment is not None:
        cmd.extend(('-c', comment))

    if home is not None:
        cmd.extend(('-d', home))

    if create_home is False:
        cmd.append('-M')
    elif create_home is True:
        cmd.append('-m')

    if shell:
        cmd.extend(('-s', shell))

    if system:
        cmd.append('-r')

    cmd.append(name)

    stdout, stderr, returncode = proc.run(
        cmd, status_ok=(0, 9), status_meaning=_USERADD_STATUS_CODES)

    if returncode == 9:
        # FIXME: should check if user is up-to-date (home, etc)
        return Unchanged(msg='User {} already exists'.format(name))

    info_users.invalidate_cache()
    return Changed(msg='Created user {}'.format(name))


@operation()
def userdel(name, remove_home=False, force=False):
    cmd = [config['cmd_userdel']]

    if remove_home:
        cmd.append('-r')

    if force:
        cmd.append('-f')

    cmd.append(name)

    stdout, stderr, returncode = proc.run(
        cmd, status_ok=(0, 6), status_meaning=_USERDEL_STATUS_CODES)

    if returncode == 6:
        return Unchanged(msg='User {} does not exist'.format(name))

    info_users.invalidate_cache()
    return Changed(msg='Removed user {}'.format(name))


ShadowEntryBase = namedtuple('ShadowEntryBase', [
    'name',
    'password_encrypted',
    'last_change',
    'min_age',
    'max_age',
    'warn_period',
    'inact_period',
    'expires',
    'reserved',
])


class ShadowEntry(ShadowEntryBase):
    @classmethod
    def from_line(cls, l):
        return cls(*l.split(':'))

    def to_line(self):
        return ':'.join(self)


@operation()
def set_unlocked_no_password(names):
    # FIXME: decide API guidelines, add typechecking once Python3 is available
    # example: passing a string to names will work, but result in non-sensical
    # results.
    with fs.edit('/etc/shadow', create=False) as shadow:
        new_lines = []

        for line in shadow.lines():
            entry = ShadowEntry.from_line(line)

            if entry.name in names:
                entry = entry._replace(password_encrypted='*')
                new_lines.append(entry.to_line())
            else:
                new_lines.append(line)

        shadow.set_lines(new_lines)

    if shadow.changed:
        return Changed(msg='Unlocked users {}'.format(names))

    return Unchanged(msg='Users {} already unlocked'.format(names))


@operation()
def set_password(name, password=None, hashed=False, salt=None):
    if salt is None:
        salt = hashlib.sha1(os.urandom(64)).hexdigest()

    if not hashed:
        # hash using sha256
        hash = crypt(password, "$6$" + salt)
    else:
        hash = password

    # at this point, we have a hashed password
    with fs.edit('/etc/shadow', create=False) as shadow:
        new_lines = []

        for line in shadow.lines():
            entry = ShadowEntry.from_line(line)

            if entry.name == name:
                # we need to check if the password already matches (with a
                # different salt)

                pwc = entry.password_encrypted

                need_update = True

                if hashed:
                    # we were supplied a hashed password, simply compare the
                    # hashes
                    need_update = (pwc != password)
                else:
                    # not hashed
                    if '$' in pwc:
                        lead = pwc[:pwc.rindex('$')]
                        need_update = (crypt(password, lead) != pwc)

                if need_update:
                    entry = entry._replace(password_encrypted=hash)
                    new_lines.append(entry.to_line())
                    continue

            new_lines.append(line)

        shadow.set_lines(new_lines)

    if shadow.changed:
        return Changed(msg='Updated password for user {}'.format(name))

    return Unchanged(msg='Password for {} already set'.format(name))
