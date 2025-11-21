"""Async-capable Moto context and aiobotocore patching helpers."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager, AbstractContextManager
import inspect
from typing import Any, overload, TypeVar


try:  # aioboto3 is optional
    import aioboto3.session as aioboto3_session
except ImportError:  # pragma: no cover
    aioboto3_session = None
from aiobotocore.awsrequest import AioAWSResponse
from aiobotocore.endpoint import AioEndpoint
from aiobotocore.hooks import AioHierarchicalEmitter
from aiobotocore.session import AioSession
from botocore.awsrequest import AWSResponse
from botocore.compat import HTTPHeaders
from moto.core.decorator import mock_aws as moto_mock_aws
from moto.core.models import botocore_stubber, MockAWS

from aiomoto.aioboto3_patch import patch_aioboto3_resource, restore_aioboto3_resource


T = TypeVar("T")


class _AioBytesIOAdapter:
    """Async wrapper around Moto's in-memory response body."""

    def __init__(self, raw: Any) -> None:
        self._raw = raw

    async def read(
        self, amt: int | None = None
    ) -> bytes:  # pragma: no cover - thin adapter
        data = self._raw.read() if amt is None else self._raw.read(amt)
        return data or b""


def _to_aio_response(response: AWSResponse) -> AioAWSResponse:
    """Convert Moto's synchronous AWSResponse into an awaitable variant.

    Returns:
        AioAWSResponse carrying the same metadata and an async-readable body.
    """

    headers_http = HTTPHeaders()
    for key, value in response.headers.items():
        headers_http.add_header(str(key), str(value))
    raw_adapter = _AioBytesIOAdapter(response.raw)
    return AioAWSResponse(response.url, response.status_code, headers_http, raw_adapter)


class AioBotocorePatcher:
    """Apply minimal aiobotocore patches for Moto interoperability."""

    def __init__(self) -> None:
        self._active = False
        self._original_convert: Any = None
        self._original_send: Any = None
        self._original_create_client: Any = None
        self._patched_aioboto3 = False
        self._original_aio_emitter_emit: Any = None

    def start(self) -> None:
        """Activate aiobotocore patches and start Moto's mock context."""
        if self._active:
            return
        self._active = True
        self._patch_convert()
        self._patch_send()
        self._patch_session_create()
        self._patch_aioboto3()
        self._patch_aio_emitter_emit()

    def stop(self) -> None:
        """Undo patches and stop Moto's mock context."""
        if not self._active:
            return
        self._restore_aioboto3()
        self._restore_session_create()
        self._restore_send()
        self._restore_convert()
        self._active = False

    # convert_to_response_dict -------------------------------------------------
    def _patch_convert(self) -> None:
        from aiobotocore import endpoint as aio_endpoint

        if self._original_convert is not None:
            return

        self._original_convert = aio_endpoint.convert_to_response_dict
        original_convert = self._original_convert

        async def _convert(http_response: Any, operation_model: Any) -> Any:
            if isinstance(http_response, AWSResponse) and not isinstance(
                http_response, AioAWSResponse
            ):
                http_response = _to_aio_response(http_response)
            return await original_convert(http_response, operation_model)

        aio_endpoint.convert_to_response_dict = _convert

    def _restore_convert(self) -> None:
        from aiobotocore import endpoint as aio_endpoint

        if self._original_convert is not None:
            aio_endpoint.convert_to_response_dict = self._original_convert
            self._original_convert = None

    # _send guard --------------------------------------------------------------
    def _patch_send(self) -> None:
        if self._original_send is not None:
            return

        self._original_send = AioEndpoint._send  # type: ignore[attr-defined]

        async def _guard_send(
            self: AioEndpoint, request: Any
        ) -> Any:  # pragma: no cover - executed via tests
            await asyncio.sleep(0)  # Ensure function remains awaitable for linting
            raise RuntimeError(
                "aiomoto: attempted real HTTP request while mock_aws is active"
            )

        AioEndpoint._send = _guard_send  # type: ignore[attr-defined]

    def _restore_send(self) -> None:
        if self._original_send is not None:
            AioEndpoint._send = self._original_send  # type: ignore[attr-defined]
            self._original_send = None

    # client creation ----------------------------------------------------------
    def _patch_session_create(self) -> None:
        if self._original_create_client is not None:
            return

        original_create_client = AioSession._create_client  # type: ignore[attr-defined]
        self._original_create_client = original_create_client

        async def _create_client(
            session_self: AioSession, *args: Any, **kwargs: Any
        ) -> Any:
            client = await original_create_client(session_self, *args, **kwargs)
            client.meta.events.register("before-send", botocore_stubber)
            return client

        AioSession._create_client = _create_client  # type: ignore[attr-defined]

    def _restore_session_create(self) -> None:
        if self._original_create_client is not None:
            AioSession._create_client = self._original_create_client  # type: ignore[attr-defined]
            self._original_create_client = None

    # aioboto3 integration ----------------------------------------------------
    def _patch_aioboto3(self) -> None:
        if self._patched_aioboto3 or aioboto3_session is None:
            return
        patch_aioboto3_resource(aioboto3_session)
        self._patched_aioboto3 = True

    def _restore_aioboto3(self) -> None:
        if not self._patched_aioboto3 or aioboto3_session is None:
            return
        restore_aioboto3_resource(aioboto3_session)
        self._patched_aioboto3 = False

    def _patch_aio_emitter_emit(self) -> None:
        if self._original_aio_emitter_emit is not None:
            return
        self._original_aio_emitter_emit = AioHierarchicalEmitter.emit

        def _emit_wrapped(
            self: AioHierarchicalEmitter, event_name: str, **kwargs: Any
        ) -> Any:
            coro = self._emit(event_name, kwargs, stop_on_response=False)  # type: ignore[attr-defined]
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                return asyncio.get_event_loop().run_until_complete(coro)
            else:
                return loop.create_task(coro)

        AioHierarchicalEmitter.emit = _emit_wrapped  # type: ignore[assignment,method-assign]

    def _restore_aio_emitter_emit(self) -> None:
        if self._original_aio_emitter_emit is not None:
            AioHierarchicalEmitter.emit = self._original_aio_emitter_emit  # type: ignore[method-assign]
            self._original_aio_emitter_emit = None


class _MotoAsyncContext(AbstractAsyncContextManager, AbstractContextManager):
    """Moto context usable from both sync and async code."""

    def __init__(self, reset: bool = True, remove_data: bool = True) -> None:
        self._reset = reset
        self._remove_data = remove_data
        self._moto_context: MockAWS = moto_mock_aws()
        self._patcher = AioBotocorePatcher()
        self._started = False

    def start(self, reset: bool | None = None) -> None:
        if self._started:
            self._moto_context.start(reset=reset if reset is not None else self._reset)
            return
        self._patcher.start()
        self._moto_context.start(reset=reset if reset is not None else self._reset)
        self._started = True

    def stop(self, remove_data: bool | None = None) -> None:
        if not self._started:
            return
        self._moto_context.stop(
            remove_data=remove_data if remove_data is not None else self._remove_data
        )
        self._patcher.stop()
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

    # Decorator behaviour ------------------------------------------------------
    def __call__(
        self, func: Callable[..., T], reset: bool = True, remove_data: bool = True
    ) -> Callable[..., T]:
        if inspect.iscoroutinefunction(func):

            async def _async_wrapper(*args: Any, **kwargs: Any) -> Any:
                async with _MotoAsyncContext(reset=reset, remove_data=remove_data):
                    return await func(*args, **kwargs)

            return _async_wrapper  # type: ignore[return-value]

        def _sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            with _MotoAsyncContext(reset=reset, remove_data=remove_data):
                return func(*args, **kwargs)

        return _sync_wrapper


@overload
def mock_aws(func: Callable[..., T]) -> Callable[..., T]: ...


@overload
def mock_aws(func: None = None) -> _MotoAsyncContext:  # pragma: no cover - overload
    ...


def mock_aws(
    func: Callable[..., T] | None = None,
) -> _MotoAsyncContext | Callable[..., T]:
    """Return a Moto-backed context that also patches aiobotocore.

    Mirrors Moto's ``mock_aws``: call without arguments for a context manager or
    decorate sync/async callables directly.
    """

    ctx = _MotoAsyncContext()
    if func is None:
        return ctx
    return ctx(func)
