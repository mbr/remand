from remand.lib import fs, apt
from remand import info

from jinja2 import Environment
from jinja2.loaders import FileSystemLoader

env = Environment(loader=FileSystemLoader('.'))
env.globals['info'] = info
tpl = env.get_template('mirrors.tpl')


def run():
    # create source.list.d
    fs.create_dir('/etc/apt/sources.list.d')

    if info['lsb.dist_id'] == 'Ubuntu':
        fs.upload_string(tpl.render(),
                         '/etc/apt/sources.list.d/ubuntu-mirrors.list')
    elif info['lsb.dist_id'] == 'Debian':
        raise NotImplementedError
    else:
        raise NotImplementedError

    # FIXME: do not do this for raspbian, needs os-release check
    fs.remove_file('/etc/apt/sources.list')

    apt.update(max_age=60)
    apt.update(max_age=60)
    apt.update(max_age=60)

    # - name: Perform dist-upgrade
    #   apt: upgrade=dist

    # - name: Install unattended-upgrades
    #   apt: pkg=unattended-upgrades state=latest

    # - name: Configure unattended-upgrades
    #   template: src=unattended-upgrades.conf dest=/etc/apt/apt.conf.d/50unattended-upgrades mode=644

    # - name: Enable unattended-upgrades
    #   copy: src=auto-upgrades.conf dest=/etc/apt/apt.conf.d/20auto-upgrades mode=644


