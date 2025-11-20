"""aiomoto public API surface."""

from aiomoto.__version__ import __version__
from aiomoto.mock import mock_aws


__all__ = ["__version__", "mock_aws"]
