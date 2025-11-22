"""Unified context manager that applies all aiomoto patches."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from contextlib import AbstractAsyncContextManager, AbstractContextManager
from functools import wraps
import inspect
from typing import Any, no_type_check, overload, ParamSpec, TypeVar


try:
    import aioboto3.session as aioboto3_session
except ImportError:  # pragma: no cover
    aioboto3_session = None  # type: ignore[assignment]

from moto.core.decorator import mock_aws as moto_mock_aws
from moto.core.models import MockAWS

from aiomoto.patches.aioboto3 import Aioboto3Patcher
from aiomoto.patches.core import CorePatcher


P = ParamSpec("P")
R = TypeVar("R")
RA = TypeVar("RA")


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

    # Decorator protocol ------------------------------------------------------
    @overload
    def __call__(
        self, func: Callable[P, Coroutine[Any, Any, RA]]
    ) -> Callable[P, Coroutine[Any, Any, RA]]: ...

    @overload
    def __call__(self, func: Callable[P, R]) -> Callable[P, R]: ...

    @no_type_check
    def __call__(self, func: Callable[P, object]) -> Callable[P, object]:
        """Allow ``@mock_aws()`` on sync or async callables.

        The same context instance wraps each invocation, starting Moto before the
        function runs and stopping it afterwards. This keeps decorator semantics in
        line with the context manager without duplicating state handling.

        Returns:
            A callable that executes the wrapped function inside the mock context.
        """

        if inspect.iscoroutinefunction(func):
            async_func = func

            @wraps(func)
            async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> object:
                async with self:
                    return await async_func(*args, **kwargs)

            return async_wrapper

        sync_func = func

        @wraps(sync_func)
        def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> object:
            with self:
                return sync_func(*args, **kwargs)

        return sync_wrapper


def mock_aws_decorator(
    *, reset: bool = True, remove_data: bool = True
) -> _MotoAsyncContext:
    """Return a decorator that wraps callables in ``mock_aws``.

    This is a convenience factory that mirrors Moto's ``@mock_aws`` decorator while
    reusing the shared async-aware context manager.
    """

    return _MotoAsyncContext(reset=reset, remove_data=remove_data)
