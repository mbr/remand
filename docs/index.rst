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


Named hosts
~~~~~~~~~~~

Inside the configuration files (see :ref:`configuration` for details), it is
possible to name specific hosts are configure them. Here is an example::

    [Host:webserver]
    hostname=10.0.1.23
    login_user=web

As a result, you can now address use the name ``webserver`` instead of a URI,
which will connect using SSH (the default transport) to ``10.0.1.23`` and login
as ``web``.


Shortcuts
~~~~~~~~~

To make matters simpler, if you give a non-existant hostname, it will be
expanded to ``ssh://...`` automatically. If ``web.example.com`` is not a host
name in the configuration files, remand will assume you meant
``ssh://web.example.com``.


.. toctree::
   :maxdepth: 2
