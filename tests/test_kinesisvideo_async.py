from __future__ import annotations

from typing import Any, TYPE_CHECKING

import aioboto3
from botocore.exceptions import ClientError
import pytest

from aiomoto import mock_aws


if TYPE_CHECKING:
    from aioboto3.client import ClientCreatorContext


def _client(region: str = "us-west-2") -> ClientCreatorContext[Any]:
    return aioboto3.Session().client("kinesisvideo", region_name=region)


@pytest.mark.asyncio
async def test_create_and_list_streams_async() -> None:
    with mock_aws():
        async with _client() as client:
            stream = await client.create_stream(StreamName="mystream")
            streams = await client.list_streams()

    assert "StreamARN" in stream
    assert any(s["StreamName"] == "mystream" for s in streams["StreamInfoList"])


@pytest.mark.asyncio
async def test_delete_stream_async() -> None:
    with mock_aws():
        async with _client() as client:
            stream = await client.create_stream(StreamName="todelete")
            await client.delete_stream(StreamARN=stream["StreamARN"])
            with pytest.raises(ClientError):  # pragma: no branch
                await client.describe_stream(StreamName="todelete")
