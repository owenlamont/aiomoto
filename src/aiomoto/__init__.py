"""aiomoto public API surface."""

from aiomoto.__version__ import __version__
from aiomoto.context import mock_aws, mock_aws_decorator
from aiomoto.exceptions import (
    AutoEndpointError,
    InProcessModeError,
    ModeConflictError,
    ProxyModeError,
    RealHTTPRequestBlockedError,
    ServerModeConfigurationError,
    ServerModeDependencyError,
    ServerModeEndpointError,
    ServerModeHealthcheckError,
    ServerModePortError,
    ServerModeRequiredError,
)
from aiomoto.patches.server_mode import AutoEndpointMode


__all__ = [
    "AutoEndpointError",
    "AutoEndpointMode",
    "InProcessModeError",
    "ModeConflictError",
    "ProxyModeError",
    "RealHTTPRequestBlockedError",
    "ServerModeConfigurationError",
    "ServerModeDependencyError",
    "ServerModeEndpointError",
    "ServerModeHealthcheckError",
    "ServerModePortError",
    "ServerModeRequiredError",
    "__version__",
    "mock_aws",
    "mock_aws_decorator",
]
