from __future__ import annotations

import pytest

from aiomoto import mock_aws


def test_mock_context_start_stop_idempotent() -> None:
    ctx = mock_aws()
    ctx.start()
    ctx.start()  # already started branch
    ctx.stop()
    ctx.stop()  # not started branch


def test_stop_is_noop_when_not_started() -> None:
    ctx = mock_aws()
    ctx.stop()  # should simply return when depth is zero


@pytest.mark.asyncio
async def test_async_context_invokes_patchers() -> None:
    ctx = mock_aws()
    tracker = {"start": 0, "stop": 0}

    class DummyPatcher:
        def start(self) -> None:
            tracker["start"] += 1

        def stop(self) -> None:
            tracker["stop"] += 1

    ctx._aioboto3 = DummyPatcher()  # type: ignore[assignment]

    async with ctx:
        assert tracker["start"] == 1
        assert ctx._started is True

    assert tracker["stop"] == 1
    assert ctx._started is False


def test_context_handles_absent_aioboto3() -> None:
    ctx = mock_aws()
    ctx._aioboto3 = None
    ctx.start()
    ctx.stop()
