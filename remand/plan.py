from contextlib import closing
from collections import Mapping
import hashlib
import imp
import os
import re
import requests
import uuid
import sys

import click
from jinja2 import Environment, FileSystemLoader, TemplateNotFound

from . import config, log, info
from .configfiles import app_dirs
from .util import ConfigParser

INVALID_CHARS = re.compile('[^A-Za-z0-9_]')


class ResourceHandlerMixin(Mapping):
    def __init__(self, plan, attr_name=None):
        self.plan = plan
        self.attr_name = attr_name

    def _load_item(self, name):
        raise NotImplementedError

    def __getitem__(self, name):
        item = self._load_item(name)

        # return our item
        if item is not None:
            return item

        # return item from a dependency
        for dep in self.plan.dependencies:
            item = getattr(dep, self.attr_name)._load_item(name)

            if item is not None:
                return item

        # nothing found, key error
        raise KeyError(name)

    def __len__(self):
        raise NotImplementedError

    def __iter__(self):
        raise NotImplementedError


class FileResourceHandler(ResourceHandlerMixin):
    def __init__(self, plan, subdir, attr_name=None):
        super(FileResourceHandler, self).__init__(plan, attr_name or subdir)
        self.subdir = subdir or ''

    def _load_item(self, name):
        if self.plan.resource_dir:
            path = os.path.join(self.plan.resource_dir, self.subdir, name)
            if os.path.exists(path):
                return path


class WebResourceHandler(ResourceHandlerMixin):
    def __init__(self, plan, attr_name):
        super(WebResourceHandler, self).__init__(plan, attr_name)
        self.urls = {}

    def _load_from_ini(self, plan):
        # load webfiles
        ini_file = os.path.join(plan.resource_dir, 'webfiles.ini')

        if os.path.exists(ini_file):
            web_ini = ConfigParser()
            web_ini.read(ini_file)

            for fn in web_ini.sections():
                section = dict(web_ini.items(fn))

                url = section['url']
                hashtype, hashsum = None, None

                if 'sha1' in section:
                    hashtype = 'sha1'
                    hashsum = section['sha1']

                if 'sha256' in section:
                    hashtype = 'sha256'
                    hashsum = section['sha256']

                self.add_url(fn, url, hashtype, hashsum)

    @property
    def storage(self):
        cache_dir = config.get('download_cache', '') or app_dirs.user_cache_dir

        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir)

        return cache_dir

    def add_url(self, name, url, hashtype, hashsum):
        self.urls[name] = (url, hashtype, hashsum)

    def download(self, name):
        url, hashtype, hashsum = self.urls[name]

        filename = os.path.join(self.storage, hashsum, name)
        d = os.path.dirname(filename)
        if not os.path.exists(d):
            os.makedirs(d)

        if os.path.exists(filename):
            log.debug('Already downloaded: {}'.format(name))
            return filename

        log.info('Downloading and verifying {}'.format(url))
        h = getattr(hashlib, hashtype)()

        with click.open_file(filename, 'wb', lazy=True, atomic=True) as\
                out, closing(requests.get(url, stream=True)) as resp:
            resp.raise_for_status()

            for chunk in resp.iter_content(config['buffer_size']):
                h.update(chunk)
                out.write(chunk)

            digest = h.hexdigest()
            if digest != hashsum:
                # click's open_file should delete on exception, but does not
                out.close()
                os.unlink(filename)
                raise ValueError(
                    'Downloaded file {} has {} hashsum of {}, expected {}'
                    .format(url, hashtype, digest, hashsum))
            log.debug('{}-hash ok for {}: {}'.format(hashtype, filename,
                                                     hashsum))

        return filename

    def _load_item(self, name):
        if name not in self.urls:
            return None
        return self.download(name)


class TemplateResourceHandler(ResourceHandlerMixin):
    def __init__(self, plan, template_dir, attr_name=None):
        super(TemplateResourceHandler, self).__init__(plan, attr_name or
                                                      template_dir)
        self.template_dir = template_dir
        self._jinja_env = None

    @property
    def jinja_env(self):
        # initialize once resource dir is known
        if self._jinja_env is None:
            if self.plan.resource_dir is None:
                raise ValueError('jinja_env requested, but no resource_dir '
                                 'set')
            self._jinja_env = Environment(loader=FileSystemLoader(os.path.join(
                self.plan.resource_dir, 'templates')))

            # add globals
            self._jinja_env.globals['config'] = config
            self._jinja_env.globals['info'] = info
        return self._jinja_env

    def render(self, name, **kwargs):
        return self[name].render(**kwargs)

    def _load_item(self, name):
        try:
            return self.jinja_env.get_template(name)
        except TemplateNotFound:
            return None


class Plan(object):
    def __init__(self, name, resource_dir=None):
        self.name = name
        self.resource_dir = None
        if resource_dir is not None:
            self.set_resouce_dir(resource_dir)

        self.objectives = {}
        self.dependencies = []

        self.files = FileResourceHandler(self, 'files')
        self.webfiles = WebResourceHandler(self, 'webfiles')
        self.templates = TemplateResourceHandler(self, 'templates')

        # FIXME: this needs cleanup, badly
        if self.resource_dir:
            self.webfiles._load_from_ini(self)

    def __repr__(self):
        return '{}({!r})'.format(self.__class__.__name__, self.name)

    def set_resouce_dir(self, resource_dir):
        self.resource_dir = os.path.abspath(resource_dir)

    def depends_on(self, plan):
        self.dependencies.append(plan)

    def execute(self, objective=None):
        # executes the objective
        if objective is None:
            if len(self.objectives) != 1:
                raise ValueError('No objective given, but plan {} has {} '
                                 'objectives'.format(self, len(
                                     self.objectives)))

            objective = self.objectives.values()[0]
        else:
            objective = self.objectives[objective]

        # got our objective, now run it

        return objective()

    def objective(self, name=None):
        if not isinstance(name, str) and name is not None:
            raise TypeError('Objective name must be string or None')

        def _(f):
            self.objectives[name or f.__name__] = f
            return f

        return _

    @classmethod
    def load_from_file(cls, path):
        plan_id = str(uuid.uuid4()).replace('-', '')
        mod = imp.load_source('_remand_plan_' + plan_id, path)

        candidates = [item
                      for item in mod.__dict__.values()
                      if isinstance(item, cls) and mod.__name__ == item.name]

        if not candidates:
            raise ValueError('Module {} does not include a solid plan'
                             .format(path))

        if len(candidates) > 1:
            raise ValueError('Module {} contains more than one plan'
                             .format(path))

        plan = candidates[0]

        # resource_dir is None -> autodetect
        if plan.resource_dir is None:
            plan.set_resouce_dir(os.path.dirname(path))

        return plan
