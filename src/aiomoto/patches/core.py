"""Core aiobotocore/Moto patching routines."""

from __future__ import annotations

import asyncio
import contextlib
from inspect import iscoroutinefunction
from typing import Any

from aiobotocore.awsrequest import AioAWSResponse
from aiobotocore.endpoint import AioEndpoint
from aiobotocore.hooks import AioHierarchicalEmitter
from aiobotocore.session import AioSession
from botocore.awsrequest import AWSResponse
from botocore.compat import HTTPHeaders
from moto.core.models import botocore_stubber

from aiomoto.exceptions import RealHTTPRequestBlockedError


_AIO_ENDPOINT_SEND_ATTR = "_send"
_AIO_SESSION_CREATE_CLIENT_ATTR = "_create_client"
_AIO_HIERARCHICAL_EMITTER_EMIT_ATTR = "_emit"


def _infer_length(raw: Any) -> int | None:
    if hasattr(raw, "getbuffer"):
        with contextlib.suppress(Exception):  # pragma: no cover - defensive
            return len(raw.getbuffer())
    if hasattr(raw, "__len__"):
        with contextlib.suppress(Exception):  # pragma: no cover - defensive
            return len(raw)
    length = getattr(raw, "len", None)
    return int(length) if isinstance(length, int) else None


class _AioStreamReader:
    """Async stand-in for aiohttp's ``StreamReader`` (``ClientResponse.content``).

    ``StreamingBody.read(amt)`` delegates to ``raw.content.read(amt)``, so this
    object accepts the size argument that aiohttp's ``StreamReader`` supports. The
    enclosing :class:`_AioBytesIOAdapter` (which mirrors ``aiohttp.ClientResponse``)
    deliberately does not, so context-manager misuse is surfaced rather than masked.
    """

    def __init__(self, raw: Any, length: int | None) -> None:
        self._raw = raw
        self._length = length
        self._eof = False

    def _update_eof(self) -> None:
        if self._length is not None and hasattr(self._raw, "tell"):
            with contextlib.suppress(Exception):  # pragma: no cover - defensive
                self._eof = self._raw.tell() >= self._length

    def at_eof(self) -> bool:
        self._update_eof()
        return self._eof

    async def read(self, n: int = -1) -> bytes:
        data = self._raw.read() if n < 0 else self._raw.read(n)
        if data is None:
            data = b""
        if isinstance(data, bytes):
            data_bytes = data
        elif isinstance(data, bytearray):  # pragma: no cover - defensive
            data_bytes = bytes(data)
        else:  # pragma: no cover - defensive
            data_bytes = bytes(data)
        self._update_eof()
        return data_bytes

    def close(self) -> None:
        self._eof = True


class _AioBytesIOAdapter:
    """Async stand-in for the ``aiohttp.ClientResponse`` Moto would return.

    aiobotocore's ``StreamingBody`` holds this object as its ``raw_stream``, so it
    must expose the surface ``StreamingBody`` reads from a ``ClientResponse``: a
    ``content`` stream reader (``raw.content.read``), an ``at_eof`` helper, and a
    ``url`` attribute. ``read`` mirrors ``aiohttp.ClientResponse.read`` and takes no
    size argument; sized reads arrive via ``StreamingBody.read(amt)``, which
    delegates to ``content.read(amt)``. Some callers (for example s3fs) also expect
    ``close``; the adapter forwards it to the underlying raw object when available.
    """

    def __init__(self, raw: Any, url: str) -> None:
        self._raw = raw
        self.url = url
        self.content = _AioStreamReader(raw, _infer_length(raw))
        self.closed = False

    def at_eof(self) -> bool:
        return self.content.at_eof()

    async def read(self) -> bytes:
        """Read the full response body, mirroring ``aiohttp.ClientResponse.read``.

        Returns:
            bytes: The remaining response payload.
        """
        return await self.content.read(-1)

    def close(self) -> None:
        close_fn = getattr(self._raw, "close", None)
        if close_fn:
            with contextlib.suppress(Exception):  # pragma: no cover - defensive
                close_fn()
        self.content.close()
        self.closed = True

    async def __aenter__(self) -> _AioBytesIOAdapter:
        return self

    async def __aexit__(
        self, _exc_type: Any, _exc: BaseException | None, _tb: Any
    ) -> bool:
        self.close()
        return False


async def _materialize_request_body(request: Any) -> None:
    """Resolve coroutine bodies used by aiobotocore into raw bytes for Moto."""

    body = getattr(request, "body", None)
    body_bytes: bytes | None = None

    if asyncio.iscoroutine(body):
        body_bytes = await body
    else:
        read_fn = getattr(body, "read", None)
        if read_fn and iscoroutinefunction(read_fn):
            body_bytes = await read_fn()

    if body_bytes is not None:
        request.body = body_bytes


def _wrap_stubber_handler(original_handler: Any) -> Any:
    """Create an async before-send handler that normalises responses for Moto.

    Returns:
        Callable[..., Awaitable[Any]]: handler compatible with aiobotocore events.
    """

    async def _stubber(event_name: str, request: Any, **kwargs: Any) -> Any:
        await _materialize_request_body(request)
        response = original_handler(event_name, request, **kwargs)
        if isinstance(response, AWSResponse) and not isinstance(
            response, AioAWSResponse
        ):
            return _to_aio_response(response)
        return response

    return _stubber


def _to_aio_response(response: AWSResponse) -> AioAWSResponse:
    headers_http = HTTPHeaders()
    for key, value in response.headers.items():
        headers_http.add_header(str(key), str(value))
    return AioAWSResponse(
        response.url,
        response.status_code,
        headers_http,
        _AioBytesIOAdapter(response.raw, response.url),
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
                http_response = _to_aio_response(
                    http_response
                )  # pragma: no cover - defensive
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

        self._original_send = getattr(AioEndpoint, _AIO_ENDPOINT_SEND_ATTR)

        async def _guard_send(self: AioEndpoint, request: Any) -> Any:
            await asyncio.sleep(0)
            raise RealHTTPRequestBlockedError(
                "aiomoto: attempted real HTTP request while mock_aws is active"
            )

        setattr(AioEndpoint, _AIO_ENDPOINT_SEND_ATTR, _guard_send)

    def _restore_send(self) -> None:
        if self._original_send is not None:
            setattr(AioEndpoint, _AIO_ENDPOINT_SEND_ATTR, self._original_send)
            self._original_send = None

    # client creation ----------------------------------------------------------
    def _patch_session_create(self) -> None:
        if self._original_create_client is not None:
            return

        original_create_client = getattr(AioSession, _AIO_SESSION_CREATE_CLIENT_ATTR)
        self._original_create_client = original_create_client

        async def _create_client(
            session_self: AioSession, *args: Any, **kwargs: Any
        ) -> Any:
            client = await original_create_client(session_self, *args, **kwargs)

            with contextlib.suppress(Exception):
                client.meta.events.unregister("before-send", botocore_stubber)

            client.meta.events.register(
                "before-send", _wrap_stubber_handler(botocore_stubber)
            )
            return client

        setattr(AioSession, _AIO_SESSION_CREATE_CLIENT_ATTR, _create_client)

    def _restore_session_create(self) -> None:
        if self._original_create_client is not None:
            setattr(
                AioSession,
                _AIO_SESSION_CREATE_CLIENT_ATTR,
                self._original_create_client,
            )
            self._original_create_client = None

    # emitter bridging ---------------------------------------------------------
    def _patch_aio_emitter_emit(self) -> None:
        if self._original_aio_emitter_emit is not None:
            return
        self._original_aio_emitter_emit = AioHierarchicalEmitter.emit

        def _emit_wrapped(
            self: AioHierarchicalEmitter, event_name: str, **kwargs: Any
        ) -> Any:
            emit_impl = getattr(self, _AIO_HIERARCHICAL_EMITTER_EMIT_ATTR)
            coro = emit_impl(event_name, kwargs, stop_on_response=False)
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:  # pragma: no cover - fallback
                return asyncio.get_event_loop().run_until_complete(
                    coro
                )  # pragma: no cover - fallback
            else:
                return loop.create_task(coro)

        AioHierarchicalEmitter.emit = _emit_wrapped

    def _restore_aio_emitter_emit(self) -> None:
        if self._original_aio_emitter_emit is not None:
            AioHierarchicalEmitter.emit = self._original_aio_emitter_emit
            self._original_aio_emitter_emit = None
