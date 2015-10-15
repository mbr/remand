import click
import logbook
from logbook.more import ColorizedStderrHandler

from . import _context
from .configfiles import HostRegistry, load_configuration
from .exc import RemandError, TransportError
from .plan import Plan
from .lib import InfoManager, proc
from .remotes.ssh import SSHRemote
from .remotes.local import LocalRemote
from .remotes.vagrant import VagrantRemote
from .uri import Uri


# medium-term, this could become a plugin-based solution, if there's need
all_transports = {
    'ssh': SSHRemote,
    'local': LocalRemote,
    'vagrant': create_vagrant_remote,
}

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


@cli.command(help='Runs a plan on a number of servers')
@click.argument('plan', type=click.Path(exists=True))
@click.argument('uris', default=None, nargs=-1, type=Uri.from_string)
@click.pass_obj
def run(obj, plan, uris):
    plan = Plan.load_from_file(plan)
    # load plan
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
            _context.top['current_plan'] = plan

            transport_cls = all_transports.get(cfg['uri'].transport, None)
            if not transport_cls:
                raise TransportError('Unknown transport: {}'.format(
                    cfg['uri']))

            log.notice('Executing {} on {}'.format(plan, cfg['uri']))

            # instantiate remote
            transport = transport_cls()
            _context.top['remote'] = transport
            if cfg.get_bool('use_sudo'):
                log.debug('using sudo to execute plan')
                with proc.sudo():
                    plan.execute()
            else:
                plan.execute()
        except RemandError, e:
            log.error(str(e))
        finally:
            _context.pop()
