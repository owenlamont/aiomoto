"""aiomoto public API surface."""

from aiomoto.__version__ import __version__
from aiomoto.context import _MotoAsyncContext, mock_aws_decorator


mock_aws = _MotoAsyncContext

__all__ = ["__version__", "mock_aws", "mock_aws_decorator"]
