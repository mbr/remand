from collections import Mapping
import os
import re
import uuid

import imp

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


class Plan(object):
    def __init__(self, name, resource_dir=None):
        self.name = name
        self.resource_dir = resource_dir
        self.objectives = {}
        self.dependencies = []

        self.files = PlanResourceHandler(self, 'files')

    def depends_on(self, plan):
        self.dependencies.append(plan)

    def objective(self, name=None):
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
            plan.resource_dir = os.path.dirname(path)

        return plan
