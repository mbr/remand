.. include:: ../README.rst

Core concepts
-------------

Remand is used to configure *hosts* that are reached by a *transport*. These
two are addressed by a URI like this::

    ssh://root@example.com:22

This URI would cause remand to connect to ``example.com`` using SSH on Port 22
and attempt to login as the ``root`` user. Note that 22 is the default port and
``root`` the default user, so the URI above can be shortened to
``ssh://example.com``.


Named hosts and shortcuts
~~~~~~~~~~~~~~~~~~~~~~~~~

Inside the configuration files (see :doc:`configuration` for details), it is
possible to name specific hosts are configure them. Here is an example::

    [Host:web.example.com]
    user=web

To make matters simpler, if you give a non-existant hostname, it will be
expanded to ``ssh://...`` automatically. If ``web.example.com`` is not a host
name in the configuration files, remand will assume you meant
``ssh://web.example.com``.


Modules
~~~~~~~

Modules are the "scripts" that are run to configure the remote server. They are
named *modules* because that is what they actually are - python modules that
are imported and executed. Details on how to write a module can be found in
:doc:`modules`.


Transports
~~~~~~~~~~

A module does not care about how the remote server is reached, it just calls
methods on a transport. The transport is responsible for making sure the
low-level actions are carried out. Currently there are two transports,
``ssh://``, which is the default and ``local://``, which will execute commands
locally.


Table of contents
-----------------

.. toctree::
   :maxdepth: 3

   Core concepts <self>
   modules
   configuration
   errors
   low-level-api
