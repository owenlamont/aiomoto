"""Unified context manager that applies all aiomoto patches."""

from __future__ import annotations

from contextlib import AbstractAsyncContextManager, AbstractContextManager
from typing import Any


try:
    import aioboto3.session as aioboto3_session
except ImportError:  # pragma: no cover
    aioboto3_session = None  # type: ignore[assignment]

from moto.core.decorator import mock_aws as moto_mock_aws
from moto.core.models import MockAWS

from aiomoto.patches.aioboto3 import Aioboto3Patcher
from aiomoto.patches.core import CorePatcher


class _MotoAsyncContext(AbstractAsyncContextManager, AbstractContextManager):
    """Moto context usable from both sync and async code."""

    def __init__(self, reset: bool = True, remove_data: bool = True) -> None:
        self._reset = reset
        self._remove_data = remove_data
        self._moto_context: MockAWS = moto_mock_aws()
        self._core = CorePatcher()
        self._aioboto3 = Aioboto3Patcher(aioboto3_session) if aioboto3_session else None
        self._started = False

    def start(self, reset: bool | None = None) -> None:
        if self._started:
            self._moto_context.start(reset=reset if reset is not None else self._reset)
            return
        self._core.start()
        if self._aioboto3:
            self._aioboto3.start()
        self._moto_context.start(reset=reset if reset is not None else self._reset)
        self._started = True

    def stop(self, remove_data: bool | None = None) -> None:
        if not self._started:
            return
        self._moto_context.stop(
            remove_data=remove_data if remove_data is not None else self._remove_data
        )
        if self._aioboto3:
            self._aioboto3.stop()
        self._core.stop()
        self._started = False

    # Sync context protocol ----------------------------------------------------
    def __enter__(self) -> _MotoAsyncContext:
        self.start()
        return self

    def __exit__(self, *args: Any) -> None:
        self.stop()

    # Async context protocol ---------------------------------------------------
    async def __aenter__(self) -> _MotoAsyncContext:
        self.start()
        return self

    async def __aexit__(self, *args: Any) -> None:
        self.stop()
