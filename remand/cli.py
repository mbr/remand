import configparser
import imp
import os
import re

import click
from click import BadParameter
import logbook
from logbook.more import ColorizedStderrHandler
from stuf.collects import ChainMap

from . import _context
from .remotes.ssh import SSHRemote
from .exc import RemandError, TransportError

# medium-term, this could become a plugin-based solution, if there's need
all_transports = {
    'ssh': SSHRemote,
}

# core logger
log = logbook.Logger('remand')

APP_NAME = 'remand'
CONFIG_INI_PATH = os.path.join(click.get_app_dir(APP_NAME), 'config.ini')

URI_RE = re.compile(r'(?:(?P<transport>[a-zA-Z][a-zA-Z0-9]*)://)?' +
                    r'(?P<host>[^/:]*)' + r'(?::(?P<port>[0-9]+))?' +
                    r'(?:(?P<path>/[^:]*))?' +
                    r'$')


class Uri(object):
    ATTRIBS = ('transport', 'host', 'port', 'path')

    def __init__(self):
        self.transport = None
        self.host = None
        self.port = None
        self.path = None

    @classmethod
    def from_string(cls, s):
        m = URI_RE.match(s)
        if not m:
            raise ValueError('Not a valid uri: {}'.format(s))

        uri = cls()

        for k, v in m.groupdict().iteritems():
            setattr(uri, k, v)

        if uri.port is not None:
            uri.port = int(uri.port)

        return uri

    @classmethod
    def from_dict(cls, d):
        uri = cls()

        for k in cls.ATTRIBS:
            if k in d:
                setattr(uri, k, d[k])

        if uri.port is not None:
            uri.port = int(uri.port)

        return uri

    def __str__(self):
        buf = []
        if self.transport is not None:
            buf.append(self.transport)
            buf.append('://')

        if self.host is not None:
            buf.append(self.host)

        if self.port is not None:
            buf.append(':')
            buf.append(str(self.port))

        if self.path is not None:
            buf.append(self.path)

        return ''.join(buf)

    def as_dict(self):
        d = {}

        for k in self.ATTRIBS:
            v = getattr(self, k)
            if v is not None:
                d[k] = v

        return d


def validate_uris(ctx, param, value):
    """Parse a list of host address parameters."""
    hs = []

    for uri in value:
        try:
            hs.append(Uri.from_string(uri))
        except ValueError:
            raise BadParameter('{} is not a valid URI'.format(uri))

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
        CONFIG_INI_PATH,
    ]
    fns.extend(configfiles)

    cfg = configparser.ConfigParser(allow_no_value=True)
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
        return ChainMap(*[sect for exp, sect in self.host_res
                          if exp.match(hostname)])


@click.command()
@click.argument('module', type=click.Path(exists=True))
@click.argument('uris', default=None, nargs=-1, callback=validate_uris)
@click.option('configfiles', '--config', '-c', envvar='REMAND_CONFIG',
              multiple=True, type=click.Path())
def remand(module, uris, configfiles):
    handler = ColorizedStderrHandler()

    with handler.applicationbound():
        # read configuration
        global_cfg = load_configuration(configfiles)

        # set up host-specific config
        host_reg = HostRegistry(global_cfg)

        # instantiate the module
        active_mod = imp.load_source('_remand_active_mod', module)

        for uri in uris:
            _context.push({})
            try:
                # lookup host
                cfg = host_reg.get_config_for_host(uri.host)

                # add layer for our values
                cfg = cfg.new_child()

                # construct new uri
                _tmp = cfg.new_child()
                _tmp.update(uri.as_dict())

                cfg['uri'] = Uri.from_dict(_tmp)

                # create thread-locals:
                _context.top['config'] = cfg
                _context.top['log'] = log

                if not cfg['uri'].transport in all_transports:
                    raise TransportError('Unknown transport: {}'.format(
                        cfg['uri'])
                    )

                log.notice('Executing {} on {}'.format(module, cfg['uri']))

                # instantiate remote
                #remote = all_transports[remote_type(address)
                _context.top['remote'] = remote

                log.debug('Running {}'.format(active_mod.__file__))
                active_mod.run()
            except RemandError, e:
                log.error(str(e))
            finally:
                _context.pop()


@click.group()
def rutil():
    pass


@rutil.command()
def config_path():
    click.echo(CONFIG_INI_PATH)
