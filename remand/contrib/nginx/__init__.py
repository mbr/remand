import os

from remand.lib import fs, proc, systemd

from remand import Plan, operation, Changed, Unchanged, info
from remand.util import any_changed

nginx = Plan(__name__, os.path.dirname(__file__))


@operation()
def enable_letsencrypt(auto_reload=True, remove_default=True):
    changed = any_changed(
        fs.upload_file(nginx.files['acme-challenge'],
                       '/etc/nginx/sites-available/acme-challenge'),
        fs.symlink('/etc/nginx/sites-available/acme-challenge',
                   '/etc/nginx/sites-enabled/00_acme-challenge'), )

    fs.create_dir('/var/www/html/.well-known')
    fs.create_dir('/var/www/html/.well-known/acme-challenge')
    fs.chmod('/var/www/html/.well-known', mode=0o555)
    fs.chmod('/var/www/html/.well-known/acme-challenge', mode=0o555)

    if remove_default:
        changed |= fs.remove_file('/etc/nginx/sites-enabled/default').changed

    if changed:
        if auto_reload:
            systemd.reload_unit('nginx.service', only_if_running=True)

        return Changed(msg='Enabled nginx Let\'s encrypt support')
    return Unchanged(msg='nginx Let\'s encrypt support already enabled')
