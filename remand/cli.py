import configparser
import os
import re

import click
from click import BadParameter
import logbook
from logbook.more import ColorizedStderrHandler

from . import _context
from .remote.ssh import SSHRemote
from .exc import RemandError

# core logger
log = logbook.Logger('remand')


HOST_RE = re.compile('(?:(?P<user>[^:@]+)@)?'   # user@
                     '(?P<host>[^:/ ]+)'        # host
                     '(?::(?P<port>[0-9]+))?$'  # :port
                     )
APP_NAME = 'remand'


def hosts(ctx, param, value):
    """Parse a list of host address parameters."""
    hs = []

    for val in value:
        m = HOST_RE.match(val)
        if not m:
            raise BadParameter('Invalid hostname string.')

        parts = m.groupdict()
        parts['uri'] = val
        hs.append(parts)

    return hs


@click.command()
@click.argument('module', type=click.Path(exists=True))
@click.argument('hosts', default=None, metavar='[USER@]HOSTNAME[:PORT]',
                callback=hosts, nargs=-1)
@click.option('configfiles', '--config', '-c', envvar='REMAND_CONFIG',
              multiple=True, type=click.Path())
def remand(module, hosts, configfiles):
    handler = ColorizedStderrHandler()
    with handler.applicationbound():

        for host in hosts:
            _context.push({})
            try:
                # configuration read from defaults, then user config
                cfg = configparser.ConfigParser()
                cfg_files = [
                    os.path.join(os.path.dirname(__file__), 'defaults.cfg'),
                    os.path.join(click.get_app_dir(APP_NAME), 'config.ini'),
                ]
                cfg_files.extend(configfiles)
                log.debug('Trying configuration files: {}'.format(cfg_files))
                cfg_files_read = cfg.read(cfg_files)
                log.debug('Read configuration from {}'.format(cfg_files_read))

                # create thread-locals:
                _context.top['config'] = cfg
                _context.top['log'] = log

                log.notice('Executing {} on {}'.format(module, host['uri']))

                # instantiate remote
                remote = SSHRemote(username=host['user'],
                                   hostname=host['host'],
                                   port=host['port'])
                _context.top['remote'] = remote
            except RemandError, e:
                log.error(str(e))
            finally:
                _context.pop()
