import hashlib
import os

import click
import logbook
from logbook.more import ColorizedStderrHandler
import requests
from six.moves.urllib.parse import urlparse

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
    'vagrant': VagrantRemote,
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
@click.option('--pkg-path',
              '-L',
              multiple=True,
              help='Additional search paths for pkgs')
@click.option('configfiles',
              '--config',
              '-c',
              multiple=True,
              type=click.Path(),
              help='Additional configuration files to read')
@click.pass_context
def cli(context, pkg_path, configfiles, debug):
    pkg_path = list(pkg_path)
    if 'REMAND_PKG_PATH' in os.environ:
        pkg_path.extend(os.environ['REMAND_PKG_PATH'].split(os.pathsep))

    # add contrib to pkg path
    import remand.contrib as contrib
    pkg_path.append(os.path.abspath(os.path.dirname(contrib.__file__)))

    # pluginbase is imported here because just importing it breaks Crypto
    # (and with it paramiko)
    import pluginbase
    plugin_base = pluginbase.PluginBase(package='remand.ext')

    obj = context.obj = {}
    handler = ColorizedStderrHandler(
        level=logbook.DEBUG if debug else logbook.INFO)

    # setup logging
    handler.push_application()

    # read configuration and host registry
    obj['config'] = load_configuration(APP_NAME, configfiles)
    obj['hosts'] = HostRegistry(obj['config'])

    plugin_source = plugin_base.make_plugin_source(
        searchpath=list(pkg_path) + ['.'])
    obj['plugin_source'] = plugin_source


@cli.command(help='Runs a plan on a number of servers')
@click.argument('plan', type=click.Path(exists=True))
@click.argument('uris', default=None, nargs=-1, type=Uri.from_string)
@click.pass_obj
def run(obj, plan, uris):
    with obj['plugin_source']:
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
                raise TransportError('Unknown transport: {}'.format(cfg[
                    'uri']))

            log.notice('Executing {} on {}'.format(plan, cfg['uri']))

            # instantiate remote
            transport = transport_cls()
            _context.top['remote'] = transport

            use_sudo = False
            if cfg['use_sudo'] == 'auto':
                if cfg['uri'].user != 'root':
                    use_sudo = True
            else:
                use_sudo = cfg.get_bool('use_sudo')

            if use_sudo:
                log.debug('using sudo to execute plan')
                with proc.sudo():
                    plan.execute()
            else:
                plan.execute()
        except RemandError, e:
            log.error(str(e))
        finally:
            _context.pop()

    if not uris:
        log.notice('Nothing to do; no URIs given')


FILE_PY_TPL = """{project}.webfiles.add_url(
    {fn!r},
    {url!r},
    '{hashfunc}',
    '{hexdigest}'
)"""

FILE_INI_TPL = """[{fn}]
url={url}
{hashfunc}={hexdigest}
"""

# FIXME: a better way would be to cache the file immediately, instead of
#        offering -o and -O


@cli.command(help='Downloads a file and generates embedding code')
@click.argument('url')
@click.option('--save', '-O', is_flag=True)
@click.option('--output', '-o', type=click.Path(), default=None)
@click.option('--hashfunc', default='sha256')
@click.option('--project', '-p', default='project')
@click.option('--fmt',
              '-f',
              type=click.Choice(['none', 'py', 'ini']),
              default='ini')
def download_file(url, output, hashfunc, project, save, fmt):
    u = urlparse(url)

    if output:
        save = True

    if not output:
        output = u.path.rsplit('/', 1)[-1]

    h = getattr(hashlib, hashfunc)()
    print url
    fn = os.path.basename(output)

    r = requests.get(url, stream=True)
    r.raise_for_status()

    out = None
    if save:
        out = open(output, 'wb')

    try:
        for chunk in r.iter_content(4096):
            h.update(chunk)
            if out:
                out.write(chunk)
    finally:
        if out:
            out.close()

    log.info('Downloading {} to {}...'.format(url, output))
    # FIXME: wrap requests here or write generic download widget that can
    #        display a progressbar for all kinds of downloads

    if fmt == 'py':
        tpl = FILE_PY_TPL
    elif fmt == 'ini':
        tpl = FILE_INI_TPL
    else:
        tpl = None

    if tpl:
        click.echo(tpl.format(fn=fn,
                              url=url,
                              hashfunc=hashfunc,
                              hexdigest=h.hexdigest(),
                              project=project))
