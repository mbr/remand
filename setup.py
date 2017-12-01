#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os

from setuptools import setup, find_packages


def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()


setup(
    name='remand',
    version='0.4.0.dev1',
    description='Sane server provisioning.',
    long_description=read('README.rst'),
    author='Marc Brinkmann',
    author_email='git@marcbrinkmann.de',
    url='http://github.com/mbr/remand',
    license='MIT',
    packages=find_packages(exclude=['tests']),
    include_package_data=True,
    zip_safe=False,
    install_requires=[
        'appdirs',
        'six',
        'pluginbase',
        'click>=5.0',
        'logbook',
        'configparser>=3.5.0b2',
        'stuf',
        'werkzeug',
        'volatile>=1.1',
        'sshkeys',
        'paramiko',  # needs our bugfix!
        'sqlalchemy',
        'sqlalchemy-pgcatalog',
        'psycopg2',
        'contextlib2',
        # chardet is a hidden dependency of python-debian
        'python-debian',
        'chardet',
        'future',
        'requests',
        'jinja2',
        'inflection',
    ],
    # FIXME: should guarantee that some packages like
    # volatile are installed
    entry_points="""
        [console_scripts]
        remand=remand.cli:cli
    """)
