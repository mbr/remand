import os

from remand.lib import apt, fs

from remand import Plan, operation, Changed, Unchanged, current_plan

# FIXME: this needs a more elegant solution
docker = Plan(__name__, os.path.dirname(__file__))


@operation()
def install_docker_compose():
    # docker: install docker compose
    ch = fs.upload_file(docker.webfiles['docker-compose-Linux-x86_64'],
                        '/usr/local/bin/docker-compose').changed
    ch |= fs.chmod('/usr/local/bin/docker-compose', mode=0o755).changed

    if ch:
        return Changed(msg='Installed docker-compose')
    return Unchanged(msg='docker-compose already installed')


@operation()
def install_docker():
    # docker: needs repo, https transport and key
    ch = apt.install_packages(['apt-transport-https', 'ca-certificates'
                               ]).changed
    ch |= apt.add_apt_keys(docker.files['docker-repo-key.asc']).changed
    ch |= apt.add_repo('debian-jessie',
                       site='https://apt.dockerproject.org/repo',
                       arch=['amd64']).changed

    # remove possibly installed old version
    ch |= apt.remove_packages(['docker.io', 'lxc-docker'], purge=True).changed

    # docker: install packages
    ch |= apt.install_packages(['docker-engine']).changed

    if ch:
        return Changed(msg='Installed docker')
    return Unchanged(msg='docker already installed')
