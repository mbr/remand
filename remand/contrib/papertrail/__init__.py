import os

from remand import operation, Plan, Changed, Unchanged
from remand.lib import apt, fs, systemd

papertrail = Plan(__name__, os.path.dirname(__file__))


@operation()
def setup_rsyslog(server_addr):
    # setup papertrail
    # FIXME: this is part of remand now
    changed = False
    changed = apt.install_packages(['rsyslog-gnutls']).changed
    changed |= fs.upload_file(papertrail.files['papertrail-bundle.pem'],
                              '/etc/papertrail-bundle.pem').changed
    changed |= fs.upload_string(
        papertrail.templates.render('papertrail.conf', addr=server_addr),
        '/etc/rsyslog.d/papertrail.conf', ).changed

    if changed:
        systemd.restart_unit('rsyslog.service')
        return Changed(
            msg='Setup papertrail logging to {}'.format(server_addr))
    return Unchanged(msg='Papertrail already setup to {}'.format(server_addr))
