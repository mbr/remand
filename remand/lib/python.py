from remand import operation, remote, config, Changed, Unchanged
from remand.lib import proc

# @operation()


class VirtualEnv(object):
    def __init__(self, remote_path):
        self.remote_path = remote_path

    @operation()
    def create(self, python='python3', global_site_packages=False):
        # FIXME: check if python version and global_site_packages are correct,
        #        and correct / recreat (--clear?) otherwise

        if not remote.stat(self.python):
            args = [config['cmd_venv'], '-p', config['venv_python_path'], ]

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

    def install(self, pkgs, editable=False):
        # FIXME: collect changes

        args = [self.pip]
        if editable:
            args.append('-e')
        args.extend(pkgs)

        return proc.run(args)

    def install_requirements(self, requirements_txt):
        # FIXME: collect changes, via freeze?

        args = [self.pip, '-r', requirements_txt]
        return proc.run(args)

    def install_gitssh(self,
                       host,
                       repo,
                       user='git',
                       branch='master',
                       egg=None):
        # FIXME: with newer git versions, we'd find a way here to pass in
        #        the deployment key, which would allow not having to store
        #        the key on the server
        url = 'git+ssh://{}@{}{}@{}'.format(user, host, repo, branch)

        if egg is not None:
            url += '#egg=' + egg
