from remand import operation, remote, config, Changed, Unchanged
from remand.exc import ConfigurationError
from remand.lib import proc


class VirtualEnv(object):
    def __init__(self, remote_path):
        self.remote_path = remote_path

    @operation()
    def create(self, python='python3', global_site_packages=False):
        # FIXME: check if python version and global_site_packages are correct,
        #        and correct / recreat (--clear?) otherwise

        if not remote.stat(self.python):
            args = [
                config['cmd_venv'],
                '-p',
                python,
            ]

            if global_site_packages:
                args.append('--system-site-packages')
            else:
                args.append('--no-site-packages')

            args.append(self.remote_path)

            proc.run(args)

            return Changed(
                msg='Initialized virtualenv in {}'.format(self.remote_path))

        return Unchanged(msg='virtualenv at {} already initialized'.format(
            self.remote_path))

    def get_bin(self, name):
        return remote.path.join(self.remote_path, 'bin', name)

    @property
    def python(self):
        return self.get_bin('python')

    @property
    def pip(self):
        return self.get_bin('pip')

    @operation()
    def install(self, pkgs, upgrade=True, editable=False):
        # FIXME: collect changes

        args = [self.pip, 'install']
        if editable:
            args.append('-e')
        if upgrade:
            args.append('-U')
        args.extend(pkgs)

        proc.run(args)

        return Changed(msg='Installed packages {} into virtualenv {}'.format(
            pkgs, self.remote_path))

    @operation()
    def install_requirements(self, requirements_txt, upgrade=False):
        # FIXME: collect changes, via freeze?

        args = [self.pip, 'install', '-r', requirements_txt]
        if upgrade:
            args.append('-U')
        proc.run(args)

        return Changed(msg='Installed requirements from {} into {}'.format(
            requirements_txt, self.remote_path))

    @operation()
    def install_git(self,
                    host,
                    repo,
                    user='git',
                    branch='master',
                    egg=None,
                    upgrade=True,
                    editable=False,
                    protocol='git'):
        # FIXME: with newer git versions, we'd find a way here to pass in
        #        the deployment key, which would allow not having to store
        #        the key on the server
        if protocol in ('http', 'https'):
            url = 'git+{}://{}/{}@{}'.format(protocol, host, repo, branch)
        elif protocol == 'git':
            url = 'git+ssh://{}@{}/{}@{}'.format(user, host, repo, branch)
        else:
            raise ConfigurationError('Unknown protocol: {}'.format(protocol))

        if egg is not None:
            url += '#egg=' + egg

        # FIXME: determine changes?
        self.install([url], upgrade=upgrade, editable=editable)

        return Changed(msg='Installed {}'.format(url))
