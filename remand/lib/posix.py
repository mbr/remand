from collections import namedtuple, OrderedDict

from remand import config, remote
from remand.lib import proc, memoize
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

PasswdEntry = namedtuple('PasswdEntry', 'name,passwd,uid,gid,gecos,home,shell')


@memoize()
def info_users():
    users = OrderedDict()

    for line in remote.file('/etc/passwd', 'r'):
        u = PasswdEntry(*line.split(':'))
        users[u.name] = u

    return users


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
            cmd.append('-g', gs.pop(0))

        for g in gs:
            cmd.append('-G', g)

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
        cmd,
        status_ok=(0, 9),
        status_meaning=_USERADD_STATUS_CODES)

    if returncode == 9:
        # FIXME: should check if user is up-to-date (home, etc)
        return Unchanged(msg='User {} already exists'.format(name))

    info_users.invalidate_cache()
    return Changed(msg='Created user {}'.format(name))
