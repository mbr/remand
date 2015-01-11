class RemandError(Exception):
    """Base class for all remand-specific exceptions."""


class TransportError(RemandError):
    """Indicates an error with the transport, which is non-recoverable."""


class RemoteFailureError(RemandError):
    """Indicates an operation on the server failed, which probably can't be
    recovered."""
