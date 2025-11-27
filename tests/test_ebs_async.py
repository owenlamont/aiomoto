from __future__ import annotations

from typing import Any, TYPE_CHECKING

import aioboto3
import pytest

from aiomoto import mock_aws


if TYPE_CHECKING:
    from aioboto3.client import ClientCreatorContext


def _client() -> ClientCreatorContext[Any]:
    return aioboto3.Session().client("ebs", region_name="us-east-1")


@pytest.mark.asyncio
async def test_start_and_complete_snapshot_async() -> None:
    with mock_aws():
        async with _client() as client:
            started = await client.start_snapshot(VolumeSize=8)
            resp = await client.complete_snapshot(
                SnapshotId=started["SnapshotId"], ChangedBlocksCount=0
            )

    assert resp["Status"] == "completed"
