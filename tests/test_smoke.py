"""Basic smoke import tests for the distribution."""

from __future__ import annotations

import aiomoto


def test_package_exposes_version() -> None:
    """Ensure the package exposes a semantic version string."""
    assert hasattr(aiomoto, "__version__")
    assert isinstance(aiomoto.__version__, str)
