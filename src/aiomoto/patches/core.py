"""Core aiobotocore/Moto patching routines."""

from __future__ import annotations

import asyncio
from typing import Any

from aiobotocore.awsrequest import AioAWSResponse
from aiobotocore.endpoint import AioEndpoint
from aiobotocore.hooks import AioHierarchicalEmitter
from aiobotocore.session import AioSession
from botocore.awsrequest import AWSResponse
from botocore.compat import HTTPHeaders
from moto.core.models import botocore_stubber


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
    headers_http = HTTPHeaders()
    for key, value in response.headers.items():
        headers_http.add_header(str(key), str(value))
    return AioAWSResponse(
        response.url,
        response.status_code,
        headers_http,
        _AioBytesIOAdapter(response.raw),
    )


class CorePatcher:
    """Patch aiobotocore endpoints + emitters to route through Moto."""

    def __init__(self) -> None:
        self._original_convert: Any = None
        self._original_send: Any = None
        self._original_create_client: Any = None
        self._original_aio_emitter_emit: Any = None

    def start(self) -> None:
        """Apply all core patches."""
        self._patch_convert()
        self._patch_send()
        self._patch_session_create()
        self._patch_aio_emitter_emit()

    def stop(self) -> None:
        """Restore all core patches."""
        self._restore_session_create()
        self._restore_send()
        self._restore_convert()
        self._restore_aio_emitter_emit()

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

        async def _guard_send(self: AioEndpoint, request: Any) -> Any:
            await asyncio.sleep(0)
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

    # emitter bridging ---------------------------------------------------------
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
