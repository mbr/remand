class RemandError(Exception):
    """Base class for all remand-specific exceptions."""


class RebootNeeded(RemandError):
    """A reboot has been requested by an operation."""


class ReconnectNeeded(RemandError):
    """A reconnect has been request."""


class TransportError(RemandError):
    """Indicates an error with the transport, which is non-recoverable."""


class RemoteFailureError(RemandError):
    """Indicates an operation on the server failed, which probably can't be
    recovered."""


class RemoteFileDoesNotExistError(RemoteFailureError):
    pass


class RemotePathIsNotADirectoryError(RemoteFailureError):
    pass


class RemotePathIsNotALinkError(RemoteFailureError):
    pass


class ConfigurationError(RemandError):
    """A requested operation is not possible, no recovery."""
