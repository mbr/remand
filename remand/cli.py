import configparser
import imp
import os
import re

import click
from click import BadParameter
import logbook
from logbook.more import ColorizedStderrHandler

from . import _context
from .remotes.ssh import SSHRemote
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


def load_configuration(configfiles=[]):
    """Loads configuration information.

    Will load ``defaults.cfg`` (shipped with remand), ``config.ini`` from the
    application directory (similar to ``~/.config/remand/``) and any extra
    configuration files passed.

    :param configfiles: Additional configuration files to read.
    """
    fns = [
        os.path.join(os.path.dirname(__file__), 'defaults.cfg'),
        os.path.join(click.get_app_dir(APP_NAME), 'config.ini'),
    ]
    fns.extend(fns)

    cfg = configparser.ConfigParser(allow_no_value=True)
    log.debug('Trying configuration files: {}'.format(fns))
    log.debug('Read configuration from {}'.format(cfg.read(fns)))
    return cfg


@click.command()
@click.argument('module', type=click.Path(exists=True))
@click.argument('hosts', default=None, metavar='[USER@]HOSTNAME[:PORT]',
                callback=hosts, nargs=-1)
@click.option('configfiles', '--config', '-c', envvar='REMAND_CONFIG',
              multiple=True, type=click.Path())
def remand(module, hosts, configfiles):
    handler = ColorizedStderrHandler()

    with handler.applicationbound():

        # instantiate the module
        active_mod = imp.load_source('_remand_active_mod', module)

        for host in hosts:
            _context.push({})
            try:
                # create thread-locals:
                _context.top['config'] = load_configuration(configfiles)
                _context.top['log'] = log

                log.notice('Executing {} on {}'.format(module, host['uri']))

                # instantiate remote
                remote = SSHRemote(username=host['user'],
                                   hostname=host['host'],
                                   port=host['port'])
                _context.top['remote'] = remote

                log.debug('Running {}'.format(active_mod.__file__))
                active_mod.run()
            except RemandError, e:
                log.error(str(e))
            finally:
                _context.pop()
