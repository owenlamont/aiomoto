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
async def test_async_context_tracks_depth() -> None:
    ctx = mock_aws()

    assert ctx._started is False
    async with ctx:
        assert ctx._started is True
        async with ctx:
            assert ctx._started is True
        assert ctx._started is True
    assert ctx._started is False
