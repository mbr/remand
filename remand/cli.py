import imp

import click
import logbook
from logbook.more import ColorizedStderrHandler

from . import _context
from .configfiles import HostRegistry, load_configuration
from .exc import RemandError, TransportError
from .lib import InfoManager
from .remotes.ssh import SSHRemote
from .uri import Uri

# medium-term, this could become a plugin-based solution, if there's need
all_transports = {'ssh': SSHRemote, }

# core logger
log = logbook.Logger('remand')

APP_NAME = 'remand'


@click.group(help='Administer servers remotely')
@click.option('--debug',
              '-d',
              help='Output more debugging information',
              is_flag=True,
              default=False)
@click.option('configfiles',
              '--config',
              '-c',
              multiple=True,
              type=click.Path(),
              help='Additional configuration files to read')
@click.pass_context
def cli(context, configfiles, debug):
    obj = context.obj = {}
    handler = ColorizedStderrHandler(
        level=logbook.DEBUG if debug else logbook.INFO)

    # setup logging
    handler.push_application()

    # read configuration and host registry
    obj['config'] = load_configuration(APP_NAME, configfiles)
    obj['hosts'] = HostRegistry(obj['config'])


@cli.command(help='Runs a module on a number of servers')
@click.argument('module', type=click.Path(exists=True))
@click.argument('uris', default=None, nargs=-1, type=Uri.from_string)
@click.pass_obj
def run(obj, module, uris):
    # instantiate the module
    active_mod = imp.load_source('_remand_active_mod', module)

    for uri in uris:
        _context.push({})
        try:
            # lookup host
            cfg = obj['hosts'].get_config_for_host(uri.host)

            # add layer for our values
            cfg = cfg.new_child()

            # construct new uri
            _tmp = cfg.new_child()
            _tmp.update(uri.as_dict())

            cfg['uri'] = Uri.from_dict(_tmp)

            # create thread-locals:
            _context.top['config'] = cfg
            _context.top['log'] = log
            _context.top['state'] = {}
            _context.top['info'] = InfoManager()

            transport_cls = all_transports.get(cfg['uri'].transport, None)
            if not transport_cls:
                raise TransportError('Unknown transport: {}'.format(
                    cfg['uri']))

            log.notice('Executing {} on {}'.format(module, cfg['uri']))

            # instantiate remote
            transport = transport_cls()
            _context.top['remote'] = transport

            log.debug('Running {}'.format(active_mod.__file__))
            active_mod.run()
        except RemandError, e:
            log.error(str(e))
        finally:
            _context.pop()
