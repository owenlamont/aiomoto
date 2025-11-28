"""Unified sync/async context manager that applies all aiomoto patches.

`mock_aws` mirrors moto's flexible surface:
1) Sync or async context manager: `with mock_aws(...):` / `async with mock_aws(...):`.
2) Decorator without args: `@mock_aws`.
3) Decorator with config/flags:
   `@mock_aws(config={...}, reset=False, remove_data=False)`.

The overloads + ParamSpec/TypeVar plumbing keep typing correct for both sync and async
callables while sharing one implementation.
"""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from contextlib import AbstractAsyncContextManager, AbstractContextManager
from functools import wraps
import inspect
from typing import Any, no_type_check, overload, ParamSpec, TypeVar

from moto import settings
from moto.core.decorator import mock_aws as moto_mock_aws
from moto.core.models import MockAWS

from aiomoto.patches.core import CorePatcher


P = ParamSpec("P")
R = TypeVar("R")
RA = TypeVar("RA")


class _MotoAsyncContext(AbstractAsyncContextManager, AbstractContextManager):
    """Moto context usable from both sync and async code."""

    def __init__(
        self, reset: bool = True, remove_data: bool = True, *, config: Any | None = None
    ) -> None:
        if settings.TEST_SERVER_MODE or settings.is_test_proxy_mode():
            raise RuntimeError(
                "aiomoto supports in-process moto only; server/proxy modes are "
                "unsupported."
            )
        self._reset = reset
        self._remove_data = remove_data
        moto_kwargs: dict[str, Any] = {}
        if config is not None:
            moto_kwargs["config"] = config
        self._moto_context: MockAWS = moto_mock_aws(**moto_kwargs)
        self._core = CorePatcher()
        self._depth = 0

    @property
    def _started(self) -> bool:
        """Backwards-compat alias for previous boolean flag."""

        return self._depth > 0

    def start(self, reset: bool | None = None) -> None:
        if self._depth == 0:
            self._core.start()

        self._moto_context.start(reset=reset if reset is not None else self._reset)
        self._depth += 1

    def stop(self, remove_data: bool | None = None) -> None:
        if self._depth == 0:
            return
        self._moto_context.stop(
            remove_data=remove_data if remove_data is not None else self._remove_data
        )
        self._depth -= 1
        if self._depth == 0:
            self._core.stop()

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
    *, reset: bool = True, remove_data: bool = True, config: Any | None = None
) -> _MotoAsyncContext:
    """Return a decorator that wraps callables in ``mock_aws``.

    This is a convenience factory that mirrors Moto's ``@mock_aws`` decorator while
    reusing the shared async-aware context manager.
    """

    return _MotoAsyncContext(reset=reset, remove_data=remove_data, config=config)


@overload
def mock_aws(
    func: Callable[P, Coroutine[Any, Any, RA]], /
) -> Callable[P, Coroutine[Any, Any, RA]]: ...


@overload
def mock_aws(func: Callable[P, R], /) -> Callable[P, R]: ...


@overload
def mock_aws(
    func: None = ...,
    *,
    reset: bool = True,
    remove_data: bool = True,
    config: Any | None = None,
) -> _MotoAsyncContext: ...


def mock_aws(
    func: Callable[P, object] | None = None,
    *,
    reset: bool = True,
    remove_data: bool = True,
    config: Any | None = None,
) -> Any:
    """Factory/decorator mirroring Moto's ``mock_aws`` (config supported).

    Returns:
        A decorated callable when used as a decorator, or a context manager when
        called with no function.
    """

    context = _MotoAsyncContext(reset=reset, remove_data=remove_data, config=config)

    if func is None:
        return context

    if inspect.iscoroutinefunction(func):

        @wraps(func)
        async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> Any:
            async with context:
                return await func(*args, **kwargs)

        return async_wrapper

    @wraps(func)
    def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> Any:
        with context:
            return func(*args, **kwargs)

    return sync_wrapper
