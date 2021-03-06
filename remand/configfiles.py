import os
import re

from appdirs import AppDirs
import logbook

from .util import TypeConversionChainMap, ConfigParser

log = logbook.Logger('config')
app_dirs = AppDirs('remand', False)


def load_configuration(app_name, configfiles=[]):
    """Loads configuration information.

    Will load ``defaults.cfg`` (shipped with remand), ``config.ini`` from the
    application directory (similar to ``~/.config/remand/``) and any extra
    configuration files passed.

    :param configfiles: Additional configuration files to read.
    """
    fns = [
        os.path.join(os.path.dirname(__file__), 'defaults.cfg'),
        os.path.join(app_dirs.user_config_dir, 'config.ini'),
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
        matching_sects = [
            sect for exp, sect in self.host_res if exp.match(hostname)
        ]

        # use sections in reverse so that sections further down overwrite
        # those defined earlier
        return TypeConversionChainMap(*reversed(matching_sects))
