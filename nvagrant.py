"""Normalize vagrant.

As vagrant uses the user vagrant by default, this module will rectify that by
install a key for the root user and removing the user vagrant, if it exists.
"""

from remand import remote
from remand.lib import proc


def run():
    # we're logged in as vagrant:vagrant
    with proc.sudo():
        print proc.run('id')
        print 'hello'
        remote.file('/testf', 'w').write('yeah')
    remote.file('norights', 'w').write('foo')
