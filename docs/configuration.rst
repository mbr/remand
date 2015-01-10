Configuration files
===================

.. highlight:: ini

Configuration files are used by remand to set global options and set up rules
for hosts or groups of hosts.


Syntax
------

Every configuration file is parsed by the Python :mod:`ConfigParser` module,
which uses the ini-syntax::

    # comments need to be on their own line and prefix with a hash

    [Host:ernie.example.com]
    # on the commandline,  remand mod.py ernie.example.com  will match this
    # host and cause it to connect to port 2222 instead of the default
    port=2222
    user=ernie

    [Match:.*\.example\.com]
    # when prefixed with "Match:", a Perl-compatible regular expression must
    # follow, configuration in this section will be applied to all hosts ending
    # in ".example.com".
    user=muppet

Options are applied from top to bottom, with no regard given to whether or not
the configuration section was a ``Host`` or ``Match`` one. When requesting
``ernie.example.com``, the ``user`` value will be ``muppet``, as the
``Match:.*\.example\.com`` section will overwrite the value set earlier.


Configuration paths
-------------------

remand can process any number of configuration files. If values conflict, a
file read later will supercede an earlier one.

.. highlight:: bash

1. First, the defaults are read from ``defaults.cfg``, which ships with remand.
2. User configuration is read. To find out the platform-dependant path for the
   user configuration file, you can use the included ``rutil`` tool::

       $ rutil config_path
       /home/yourusername/.config/remand/config.ini
3. If there is an environment variable ``REMAND_CONFIG``, paths found in it
   will be read. More than one path may be supplied, distinguished by
   the platform-specific path seperator (eg. ``:`` on *nix, ``;`` on Windows).
4. Configuration files may be given using the ``--config``/``-c`` commandline
   switch, which may appear multiple times. If any are given, the processing of
   3. is skipped::

       $ remand -c localconf.ini -c 2ndconf.ini mymod.py hosta hostb ...

