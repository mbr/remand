import os

from remand.lib import fs, proc, systemd

from remand import Plan, operation, Changed, Unchanged, info

ssh_preset = Plan(__name__, os.path.dirname(__file__))


@operation()
def install_strict_ssh(allow_users=['root'],
                       allow_groups=None,
                       address_family="any",
                       permit_root=True,
                       modern_ciphers=True,
                       sftp_enabled=True,
                       agent_forwarding=False,
                       x11=False,
                       tcp_forwarding=True,
                       unix_forwarding=True,
                       tunnel=False,
                       port=22,
                       use_dns=False,
                       print_motd=False,
                       auto_restart=True,
                       check_sshd_config=True):
    # FIXME: change default in jinja templates to strict reporting of missing
    #        values to avoid creating broken ssh configs
    # FIXME: add (possibly generic) support for atomic-tested-configuration
    #        swaps (i.e. run sshd -t on a config)
    tpl = ssh_preset.templates.render('sshd_config',
                                      allow_users=allow_users,
                                      allow_groups=allow_groups,
                                      address_family=address_family,
                                      permit_root=permit_root,
                                      modern_ciphers=modern_ciphers,
                                      sftp_enabled=sftp_enabled,
                                      agent_forwarding=agent_forwarding,
                                      x11=x11,
                                      tcp_forwarding=tcp_forwarding,
                                      unix_forwarding=unix_forwarding,
                                      tunnel=tunnel,
                                      port=port,
                                      print_motd=print_motd)

    if fs.upload_string(tpl, '/etc/ssh/sshd_config').changed:
        if check_sshd_config:
            proc.run(['sshd', '-t'])

        # FIXME: we may want to abstract the init-system here
        if auto_restart:
            systemd.restart_unit('ssh.service')
        return Changed(msg='Changed sshd configuration')
    return Unchanged(msg='sshd config already strict')
