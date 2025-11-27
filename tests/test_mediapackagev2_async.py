from __future__ import annotations

from typing import Any, TYPE_CHECKING
from uuid import uuid4

import aioboto3
from botocore.exceptions import ClientError
import pytest

from aiomoto import mock_aws


if TYPE_CHECKING:
    from aioboto3.client import ClientCreatorContext


def _client(region: str = "us-east-2") -> ClientCreatorContext[Any]:
    return aioboto3.Session().client("mediapackagev2", region_name=region)


@pytest.mark.asyncio
async def test_list_channel_groups_pagination_async() -> None:
    """Ported moto mock-only test; AWS-verified ones skipped."""
    names = [str(uuid4()) for _ in range(5)]

    with mock_aws():
        async with _client("ap-southeast-1") as client:
            for group_name in names:
                await client.create_channel_group(ChannelGroupName=group_name)

            all_groups = (await client.list_channel_groups())["Items"]
            assert [group["ChannelGroupName"] for group in all_groups] == names

            page1 = await client.list_channel_groups(MaxResults=3)
            assert [group["ChannelGroupName"] for group in page1["Items"]] == names[:3]

            page2 = await client.list_channel_groups(NextToken=page1["NextToken"])
            assert [group["ChannelGroupName"] for group in page2["Items"]] == names[3:]

            # cleanup
            for group_name in names:
                await client.delete_channel_group(ChannelGroupName=group_name)


@pytest.mark.asyncio
async def test_delete_channel_group_not_empty_conflict_async() -> None:
    with mock_aws():
        async with _client() as client:
            group_name = str(uuid4())
            channel_name = str(uuid4())
            await client.create_channel_group(ChannelGroupName=group_name)
            await client.create_channel(
                ChannelGroupName=group_name, ChannelName=channel_name
            )

            with pytest.raises(ClientError):  # pragma: no branch
                await client.delete_channel_group(ChannelGroupName=group_name)

            await client.delete_channel(
                ChannelGroupName=group_name, ChannelName=channel_name
            )
            await client.delete_channel_group(ChannelGroupName=group_name)
