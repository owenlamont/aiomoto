from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

from aiobotocore.endpoint import AioEndpoint
from botocore.awsrequest import AWSResponse
from botocore.compat import HTTPHeaders
import pytest

from aiomoto import mock_aws
from aiomoto.patches.core import (
    _AioBytesIOAdapter,
    _materialize_request_body,
    _wrap_stubber_handler,
    CorePatcher,
)


class _DummyBodyWithLen:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload
        self.closed = False

    def __len__(self) -> int:
        return len(self._payload)

    def read(self, amt: int | None = None) -> bytes:
        if amt is None:
            return self._payload
        return self._payload[:amt]

    def close(self) -> None:
        self.closed = True


class _DummyBodyNone:
    def read(self, amt: int | None = None) -> None:  # pragma: no cover - defensive
        return None


@pytest.mark.asyncio
async def test_aio_bytes_io_adapter_branches() -> None:
    adapter = _AioBytesIOAdapter(_DummyBodyWithLen(b"abc"), "url")
    assert adapter._infer_length() == 3
    assert adapter.at_eof() is False
    assert await adapter.read() == b"abc"
    assert await adapter.read(2) == b"ab"
    assert adapter.at_eof() is False
    adapter.close()
    assert adapter.closed is True
    assert adapter.at_eof() is True

    async with _AioBytesIOAdapter(_DummyBodyWithLen(b"x"), "url") as cm_adapter:
        assert await cm_adapter.read() == b"x"
    assert cm_adapter.closed is True

    adapter2 = _AioBytesIOAdapter(_DummyBodyNone(), "url")
    assert await adapter2.read() == b""
    assert adapter2.at_eof() is False


@pytest.mark.asyncio
async def test_materialize_request_body_covers_coroutine_and_read() -> None:
    async def coro_body() -> bytes:
        return await asyncio.sleep(0, result=b"coro")

    class _AsyncReader:
        async def read(self) -> bytes:
            return b"reader"

    req1 = SimpleNamespace(body=coro_body())
    await _materialize_request_body(req1)
    assert req1.body == b"coro"

    req2 = SimpleNamespace(body=_AsyncReader())
    await _materialize_request_body(req2)
    assert req2.body == b"reader"


@pytest.mark.asyncio
async def test_wrap_stubber_handler_converts_sync_response() -> None:
    def handler(event_name: str, request: Any, **kwargs: Any) -> AWSResponse:
        return AWSResponse(
            "http://example", 200, HTTPHeaders(), _DummyBodyWithLen(b"data")
        )

    wrapped = _wrap_stubber_handler(handler)
    result = await wrapped("evt", SimpleNamespace(body=b"abc"))
    assert isinstance(result, AWSResponse)
    assert result.__class__.__name__ == "AioAWSResponse"

    wrapped2 = _wrap_stubber_handler(lambda *_args, **_kwargs: result)
    same = await wrapped2("evt", SimpleNamespace(body=b"abc"))
    assert same is result


def test_core_patcher_idempotent_and_guard_blocks_send() -> None:
    patcher = CorePatcher()
    patcher.start()
    patcher.start()  # idempotent branch

    guard = AioEndpoint._send  # type: ignore[attr-defined]
    with pytest.raises(RuntimeError):
        asyncio.run(guard(object(), None))

    patcher.stop()
    patcher.stop()  # idempotent restore branch


def test_mock_context_start_stop_idempotent() -> None:
    ctx = mock_aws()
    ctx.start()
    ctx.start()  # already started branch
    ctx.stop()
    ctx.stop()  # not started branch
