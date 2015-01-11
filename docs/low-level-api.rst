The low-level API
=================

Any :const:`~remand.transport` implements the :class:`~remand.remotes.Remote`
interface below. While it is possible to call these methods when writing
modules, it is not recommended to do so, rather plugins should be used.

An important distinction is the generel "intent" of these functions: Being
lower level, all instance methods of :class:`~remand.remotes.Remote` have an
imperative touch, while functions provided by plugins should be as idempotent
as possible to give them a more declarative feel.


.. autoclass:: remand.remotes.Remote
   :members:
