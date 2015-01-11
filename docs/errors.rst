Error handling and exceptions
=============================

All "regular" exceptions thrown by remand, modules or plugins are derived from
:class:`~remand.exc.RemandError`. Any exception thrown that is not wrapped in
one of these is a bug.

.. automodule:: remand.exc
   :members:
