Other Aspects
=============

.. _umask:

umask
-----

Something to keep in mind when dealing with remote servers are unusual umasks.
To combat this, remand will by default try to reset the umask on the remote
side [1]_ to ``022``, causing directories to be created with ``0755`` and files
with
``0644`` permissions.

Note that the umask is applied to all modes (other than
:func:`~remand.remotes.Remote.chmod`), which is why the default ``mode``
argument for :func:`~remand.remotes.Remote.mkdir` is ``0777``.

The local umask on the machine running remand has no effect on the remote side.

To change the behaviour from the default, the low-level
:func:`~remand.remotes.Remote.umask` function can be used, as well as the
configuration setting ``reset_umask``.

.. [1] At the moment the implementation is lagging behind and will only warn
       you about incorrect umasks. remand will either display a message about
       the mismatching umasks or work as expected.


Error handling and exceptions
-----------------------------

All "regular" exceptions thrown by remand, modules or plugins are derived from
:class:`~remand.exc.RemandError`. Any exception thrown that is not wrapped in
one of these is a bug.

.. automodule:: remand.exc
   :members:
