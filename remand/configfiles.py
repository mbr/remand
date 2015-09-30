if sys.version_info.major < 3:
    from backports.configparser import ConfigParser
else:
    from configparser import ConfigParser
import os
import re
import sys

import click
import logbook

from .util import TypeConversionChainMap

log = logbook.Logger('config')


def load_configuration(app_name, configfiles=[]):
    """Loads configuration information.

    Will load ``defaults.cfg`` (shipped with remand), ``config.ini`` from the
    application directory (similar to ``~/.config/remand/``) and any extra
    configuration files passed.

    :param configfiles: Additional configuration files to read.
    """
    fns = [
        os.path.join(os.path.dirname(__file__), 'defaults.cfg'),
        os.path.join(click.get_app_dir(app_name), 'config.ini'),
    ]

    if 'REMAND_CONFIG' in os.environ:
        fns.append(os.environ['REMAND_CONFIG'])

    fns.extend(configfiles)

    cfg = ConfigParser(allow_no_value=True)
    log.debug('Trying configuration files: {}'.format(fns))
    log.debug('Read configuration from {}'.format(cfg.read(fns)))
    return cfg


class HostRegistry(object):
    MATCH_PREFIX = 'Match:'
    HOST_PREFIX = 'Host:'

    def __init__(self, cfg):
        self.host_res = []

        for name, sect in cfg.items():
            if name.startswith(self.HOST_PREFIX):
                pattern = re.escape(name[len(self.HOST_PREFIX):])

            elif name.startswith(self.MATCH_PREFIX):
                pattern = name[len(self.MATCH_PREFIX):]
                if 'match' in sect:
                    pattern = sect['match']
            else:
                continue

            self.host_res.append((re.compile(pattern + '$'), sect))

    def get_config_for_host(self, hostname):
        return TypeConversionChainMap(*[sect for exp, sect in self.host_res
                                        if exp.match(hostname)])
