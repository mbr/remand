import hashlib
import os
import time
import sys

import click
import logbook
from logbook.more import ColorizedStderrHandler
import requests
from six.moves.urllib.parse import urlparse

from . import _context
from .configfiles import HostRegistry, load_configuration
from .exc import RemandError, TransportError, ReconnectNeeded
from .plan import Plan
from .lib import InfoManager, proc
from .remotes.chroot import ChrootRemote
from .remotes.ssh import SSHRemote
from .remotes.local import LocalRemote
from .remotes.vagrant import VagrantRemote
from .uri import Uri

# medium-term, this could become a plugin-based solution, if there's need
all_transports = {
    'ssh': SSHRemote,
    'local': LocalRemote,
    'vagrant': VagrantRemote,
    'chroot': ChrootRemote,
}

# core logger
log = logbook.Logger('remand')

APP_NAME = 'remand'


@click.group(help='Administer servers remotely')
@click.option(
    '--debug',
    '-d',
    help='Output more debugging information',
    is_flag=True,
    default=False)
@click.option(
    '--debug-ssh',
    '-D',
    help='Output paramiko debugging info when `--debug` is enabled',
    is_flag=True,
    default=False, )
@click.option(
    '--pkg-path', '-L', multiple=True, help='Additional search paths for pkgs')
@click.option(
    'configfiles',
    '--configfile',
    '-c',
    multiple=True,
    type=click.Path(),
    help='Additional configuration files to read')
@click.option(
    'confvars',
    '--config',
    '-C',
    multiple=True,
    type=click.Tuple((str, str)),
    help='Set configuration values directly')
@click.pass_context
def cli(context, pkg_path, configfiles, debug, confvars, debug_ssh):
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
    handler = ColorizedStderrHandler(level=logbook.DEBUG
                                     if debug else logbook.INFO)

    # setup logging
    logbook.compat.redirect_logging()
    handler.push_application()

    if not debug_ssh:
        logbook.NullHandler(
            filter=lambda r, h: r.channel.startswith('paramiko')
        ).push_application()

    # read configuration and host registry
    obj['config'] = load_configuration(APP_NAME, configfiles)

    # set configuration values
    for k, v in confvars:
        obj['config']['Match:.*'][k] = v
        log.debug('Set Match.*:[{!r}] = {!r}'.format(k, v))

    obj['hosts'] = HostRegistry(obj['config'])

    plugin_source = plugin_base.make_plugin_source(
        searchpath=list(pkg_path) + ['.'])
    obj['plugin_source'] = plugin_source


@cli.command(help='Runs a plan on a number of servers')
@click.argument('plan', type=click.Path(exists=True))
@click.argument('uris', default=None, nargs=-1, type=Uri.from_string)
@click.option('--objective', '-O', default=None, help='Objective name to run')
@click.pass_obj
def run(obj, plan, uris, objective):
    failures = False

    with obj['plugin_source']:
        plan = Plan.load_from_file(plan)

    # load plan
    for uri in uris:
        retry = True
        config_overlay = {}
        while retry:
            _context.push({})
            try:
                retry = False
                # lookup host
                cfg = obj['hosts'].get_config_for_host(uri.host)

                # add layer for uri values
                cfg = cfg.new_child()

                # construct new uri
                _tmp = cfg.new_child()
                _tmp.update(uri.as_dict())

                cfg['uri'] = Uri.from_dict(_tmp)

                # add another configuration layer for custom values from plans
                cfg = cfg.new_child(config_overlay)

                # create thread-locals:
                _context.top['config'] = cfg
                _context.top['log'] = log
                _context.top['state'] = {}
                _context.top['info'] = InfoManager()
                _context.top['current_plan'] = plan

                transport_cls = all_transports.get(cfg['uri'].transport, None)
                if not transport_cls:
                    raise TransportError(
                        'Unknown transport: {}'.format(cfg['uri']))

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
                        plan.execute(objective)
                else:
                    plan.execute(objective)
            except ReconnectNeeded as e:
                log.notice('A reconnect has been requested by {}'.format(e))

                if cfg.get_bool('auto_reconnect'):
                    delay = int(cfg['reconnect_delay'])
                    log.notice('Reconnecting in {} seconds'.format(delay))
                    time.sleep(delay)
                    retry = True
                    continue
                else:
                    log.error('Automatic reconnects disabled, cannot continue')
            except RemandError as e:
                log.error(str(e))
                failures = True
            finally:
                _context.pop()

    if not uris:
        log.notice('Nothing to do; no URIs given')

    if failures:
        sys.exit(1)


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


@cli.command(help='Downloads files and generates embedding code')
@click.argument('urls', nargs=-1)
@click.option('--save', '-O', is_flag=True)
@click.option('--output', '-o', type=click.Path(), default=None)
@click.option('--hashfunc', default='sha256')
@click.option('--project', '-p', default='project')
@click.option(
    '--fmt', '-f', type=click.Choice(['none', 'py', 'ini']), default='ini')
def download_file(urls, output, hashfunc, project, save, fmt):
    param_output = output

    for url in urls:
        output = param_output
        u = urlparse(url)

        if output:
            save = True

        if not output:
            output = u.path.rsplit('/', 1)[-1]

        h = getattr(hashlib, hashfunc)()
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
            click.echo(
                tpl.format(
                    fn=fn,
                    url=url,
                    hashfunc=hashfunc,
                    hexdigest=h.hexdigest(),
                    project=project))
