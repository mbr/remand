class RemandError(Exception):
    """Base class for all remand-specific exceptions."""


class TransportError(RemandError):
    """Indicates an error with the transport, which is non-recoverable."""
