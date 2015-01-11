from remand import log, remote


def run():
    log.warning('Running testing module. Do not run this on a real machine!')

    log.debug('Testing popen')
    proc = remote.popen(['uname'])
    stdout, stderr = proc.communicate()
    assert 'Linux' == stdout.strip()

    log.debug('Testing getcwd()')
    assert '/home/vagrant' == remote.getcwd()

    log.debug('Testing chdir()')
    remote.chdir('/')
    assert '/' == remote.getcwd()
    remote.chdir('/home/vagrant')

    # create a sample file
    TESTFN = 'testfile'
    TESTDN = 'TESTDIR'
    log.debug('Testing file')
    with remote.file(TESTFN, mode='w') as out:
        out.write('test')

    log.debug('Testing chmod')
    remote.chmod(TESTFN, 0732)

    log.debug('Testing mkdir')
    # FIXME: umask?
    # FIXME: on exists/conflict?
    remote.mkdir(TESTDN, 0700)

    log.debug('Testing listdir')
    assert TESTFN in remote.listdir('.')
    assert TESTDN in remote.listdir('.')

    log.debug('Testing rmdir')
    remote.rmdir(TESTDN)

    # FIXME: can't test chown without root access

    log.debug('Testing normalize')
    assert '/home' == remote.normalize('./..')

    log.debug('Testing symlink')
    remote.symlink('to', 'from')

    log.debug('Testing lstat')
    remote.lstat('from')

    log.debug('Testing readlink')
    assert remote.readlink('/home/vagrant/from') == 'to'

    log.debug('Testing rename')
    remote.rename('from', 'from2')
    assert remote.readlink('/home/vagrant/from2') == 'to'

    log.debug('Testing unlink')
    remote.unlink('/home/vagrant/from2')

    log.debug('Testing stat')
    s = remote.stat(TESTFN)
    assert s.st_uid == 1000
    assert s.st_gid == 1000
    remote.unlink(TESTFN)
