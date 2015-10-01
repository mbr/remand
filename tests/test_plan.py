import os

import pytest
from remand.plan import Plan

PLAN_DIR = os.path.join(os.path.dirname(__file__), 'plans')


@pytest.fixture
def plan_file():
    return os.path.join(PLAN_DIR, 'simple_plan.py')


@pytest.fixture
def plan(plan_file):
    return Plan.load_from_file(plan_file)


@pytest.fixture
def other_plan():
    return Plan.load_from_file(os.path.join(PLAN_DIR, 'other', 'plan.py'))


def test_invalid_load():
    with pytest.raises(ValueError):
        Plan.load_from_file(os.path.join(PLAN_DIR, 'no_plan.py'))


def test_multiple_load():
    with pytest.raises(ValueError):
        Plan.load_from_file(os.path.join(PLAN_DIR, 'multiple_plans.py'))


def test_simple_resource_loading(plan):
    assert os.path.join(PLAN_DIR, 'files', 'sample') == plan.files['sample']


def test_dependency_resource_loading(plan, other_plan):
    with pytest.raises(KeyError):
        plan.files['foo_other']

    plan.depends_on(other_plan)

    assert os.path.join(PLAN_DIR, 'other', 'files', 'foo_other')\
           == plan.files                        ['foo_other']
