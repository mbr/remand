from contextlib import closing
from collections import Mapping
import hashlib
import imp
import os
import re
import requests
import uuid

import click

from . import config, log
from .configfiles import app_dirs

INVALID_CHARS = re.compile('[^A-Za-z0-9_]')


class PlanResourceHandler(Mapping):
    def __init__(self, plan, subdir, attr_name=None):
        self.attr_name = attr_name or subdir
        self.subdir = subdir or ''
        self.plan = plan

    def __getitem__(self, name):
        if self.plan.resource_dir:
            path = os.path.join(self.plan.resource_dir, self.subdir, name)

            if os.path.exists(path):
                return path

        # no resource found or no resource dir, try deps
        for dep in self.plan.dependencies:
            try:
                return getattr(dep, self.attr_name)[name]
            except KeyError:
                pass

        # nothing found
        raise KeyError(os.path.join(self.subdir, name))

    def __len__(self):
        raise NotImplementedError

    def __iter__(self):
        raise NotImplementedError


class WebResourceHandler(Mapping):
    # FIXME: consolidate with PlanResourceHandler

    def __init__(self):
        self.urls = {}

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

    def __getitem__(self, name):
        return self.download(name)

    def __len__(self):
        raise NotImplementedError

    def __iter__(self):
        raise NotImplementedError


class Plan(object):
    def __init__(self, name, resource_dir=None):
        self.name = name
        self.resource_dir = None
        if resource_dir is not None:
            self.set_resouce_dir(resource_dir)

        self.objectives = {}
        self.dependencies = []

        self.files = PlanResourceHandler(self, 'files')
        self.webfiles = WebResourceHandler()

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

        candidates = [item for item in mod.__dict__.values()
                      if isinstance(item, cls)]

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
