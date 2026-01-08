"""Custom exception types for aiomoto."""


class AutoEndpointError(Exception):
    """Raised when server-mode auto-endpoint configuration is invalid."""


class InProcessModeError(Exception):
    """Raised when in-process mode state is invalid or unavailable."""


class ModeConflictError(Exception):
    """Raised when in-process and server-mode settings conflict."""


class ProxyModeError(Exception):
    """Raised when Moto proxy mode is requested."""


class RealHTTPRequestBlockedError(Exception):
    """Raised when a real HTTP request is attempted while mocking."""


class ServerModeConfigurationError(Exception):
    """Raised for invalid server-mode configuration."""


class ServerModeDependencyError(Exception):
    """Raised when server-mode dependencies are missing."""


class ServerModeEndpointError(Exception):
    """Raised when server-mode endpoint discovery fails."""


class ServerModeHealthcheckError(Exception):
    """Raised when a server-mode healthcheck fails."""


class ServerModePortError(Exception):
    """Raised when an invalid or conflicting server port is supplied."""


class ServerModeRequiredError(Exception):
    """Raised when server-mode is required but not enabled."""
