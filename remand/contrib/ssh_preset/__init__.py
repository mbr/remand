import os

from remand.lib import fs, systemd

from remand import Plan, operation, Changed, Unchanged

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
                       use_dns=False):
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
                                      port=port)

    if fs.upload_string(tpl, '/etc/ssh/sshd_config').changed:
        systemd.restart_unit('ssh.service')
        return Changed(msg='Changed sshd configuration')
    return Unchanged(msg='sshd config already strict')
