from re import fullmatch
from typing import Any, TYPE_CHECKING

import aioboto3
from botocore.exceptions import ClientError
import pytest

from aiomoto import mock_aws


if TYPE_CHECKING:
    from aioboto3.client import ClientCreatorContext


def _client() -> ClientCreatorContext[Any]:
    return aioboto3.Session().client("ivs", region_name="eu-west-1")


@pytest.mark.asyncio
async def test_create_channel_defaults_async() -> None:
    with mock_aws():
        async with _client() as client:
            resp = await client.create_channel(name="foo")

    channel = resp["channel"]
    assert channel["name"] == "foo"
    assert channel["authorized"] is False
    assert fullmatch(r"arn:aws:ivs:.*:channel/.*", channel["arn"])


@pytest.mark.asyncio
async def test_list_channels_filter_async() -> None:
    with mock_aws():
        async with _client() as client:
            await client.create_channel(name="foo")
            await client.create_channel(name="bar", recordingConfigurationArn="rc")

            filtered = await client.list_channels(
                filterByRecordingConfigurationArn="rc"
            )
            paged = await client.list_channels(maxResults=1)

    assert len(filtered["channels"]) == 1
    assert filtered["channels"][0]["name"] == "bar"
    assert len(paged["channels"]) == 1
    assert "nextToken" in paged


@pytest.mark.asyncio
async def test_get_channel_not_exists_async() -> None:
    with mock_aws():
        async with _client() as client:
            with pytest.raises(ClientError):  # pragma: no branch
                await client.get_channel(
                    arn="arn:aws:ivs:eu-west-1:123:channel/missing"
                )
