# -*- coding: utf-8 -*-

from better import better_theme_path

extensions = ['sphinx.ext.autodoc', 'sphinx.ext.intersphinx']
templates_path = ['_templates']
source_suffix = '.rst'
master_doc = 'index'

project = u'remand'
copyright = u'2015, Marc Brinkmann'
version = '0.1'
release = '0.1.dev1'

exclude_patterns = ['_build']
pygments_style = 'sphinx'

html_theme_path = [better_theme_path]
html_theme = 'better'
html_static_path = ['_static']

html_use_smartypants = True
html_sidebars = {'**': ['globaltoc.html', 'relations.html'], }
htmlhelp_basename = 'remanddoc'
intersphinx_mapping = {'http://docs.python.org/': None}
