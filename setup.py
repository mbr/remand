#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os

from setuptools import setup, find_packages


def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()


setup(
    name='remand',
    version='0.1dev',
    description='Sane server provisioning.',
    long_description=read('README.rst'),
    author='Marc Brinkmann',
    author_email='git@marcbrinkmann.de',
    url='http://github.com/mbr/remand',
    license='MIT',
    packages=find_packages(exclude=['tests']),
    install_requires=['six',
                      'pluginbase',
                      'click>=4.0',
                      'logbook',
                      'configparser>=3.5.0b2',
                      'stuf',
                      'werkzeug',
                      'paramiko',  # needs our bugfix!
                      # chardet is a hidden dependency of python-debian
                      'python-debian',
                      'chardet', ],
    entry_points="""
        [console_scripts]
        remand=remand.cli:cli
    """)
