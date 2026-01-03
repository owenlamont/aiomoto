"""aiomoto public API surface."""

from aiomoto.__version__ import __version__
from aiomoto.context import mock_aws, mock_aws_decorator
from aiomoto.patches.server_mode import AutoEndpointMode


__all__ = ["AutoEndpointMode", "__version__", "mock_aws", "mock_aws_decorator"]
