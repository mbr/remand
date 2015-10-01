import re
import uuid

import imp

INVALID_CHARS = re.compile('[^A-Za-z0-9_]')


class Plan(object):
    def __init__(self, name):
        self.name = name
        self.objectives = {}

    def objective(self, name=None):
        def _(f):
            self.objectives[name or f.__name__] = f
            return f

        return _

    @classmethod
    def load_from_file(cls, path):
        plan_id = str(uuid.uuid4()).replace('-', '')
        mod = imp.load_source('_remand_plan_' + plan_id, path)

        candidates = [item for item in mod.__dict__ if isinstance(item, cls)]

        if not candidates:
            raise ValueError('Module {} does not include a solid plan'
                             .format(path))

        if len(candidates):
            raise ValueError('Module {} contains more than one plan'
                             .format(path))

        plan = candidates[0]
        return plan
