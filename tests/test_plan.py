import os

import pytest
from remand.plan import Plan

PLAN_DIR = os.path.join(os.path.dirname(__file__), 'plans')


@pytest.fixture
def plan_file():
    return os.path.join(PLAN_DIR, 'sample_plan.py')


@pytest.fixture
def plan(plan_file):
    return Plan.load_from_file(plan_file)


def test_invalid_load():
    with pytest.raises(ValueError):
        Plan.load_from_file(os.path.join(PLAN_DIR, 'no_plan.py'))


def test_multiple_load():
    with pytest.raises(ValueError):
        Plan.load_from_file(os.path.join(PLAN_DIR, 'multiple_plans.py'))
