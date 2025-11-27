import json
from typing import Any, TYPE_CHECKING

import aioboto3
import pytest

from aiomoto import mock_aws


if TYPE_CHECKING:
    from aioboto3.client import ClientCreatorContext


def _client() -> ClientCreatorContext[Any]:
    return aioboto3.Session().client("resource-groups", region_name="us-east-1")


async def _create_group(client: Any) -> dict[str, Any]:
    resp: dict[str, Any] = await client.create_group(
        Name="test_resource_group",
        Description="description",
        ResourceQuery={
            "Type": "TAG_FILTERS_1_0",
            "Query": json.dumps(
                {
                    "ResourceTypeFilters": ["AWS::AllSupported"],
                    "TagFilters": [
                        {"Key": "resources_tag_key", "Values": ["resources_tag_value"]}
                    ],
                }
            ),
        },
        Tags={"resource_group_tag_key": "resource_group_tag_value"},
    )
    return resp


@pytest.mark.asyncio
async def test_create_and_delete_group_async() -> None:
    with mock_aws():
        async with _client() as client:
            response = await _create_group(client)
            assert "test_resource_group" in response["Group"]["Name"]

            deleted = await client.delete_group(GroupName="test_resource_group")
            assert deleted["Group"]["Name"] == "test_resource_group"
            listing = await client.list_groups()

    assert listing["Groups"] == []


@pytest.mark.asyncio
async def test_get_group_and_query_async() -> None:
    with mock_aws():
        async with _client() as client:
            response = await _create_group(client)
            group_name = response["Group"]["Name"]
            group_arn = response["Group"]["GroupArn"]

            by_name = await client.get_group(GroupName=group_name)
            by_arn = await client.get_group(GroupName=group_arn)

            query = await client.get_group_query(GroupName=group_name)

    assert by_name["Group"]["GroupArn"] == group_arn
    assert by_arn["Group"]["Name"] == group_name
    assert query["GroupQuery"]["ResourceQuery"]["Type"] == "TAG_FILTERS_1_0"


@pytest.mark.asyncio
async def test_tagging_async() -> None:
    with mock_aws():
        async with _client() as client:
            group = await _create_group(client)
            arn = group["Group"]["GroupArn"]

            await client.tag(
                Arn=arn, Tags={"resource_group_tag_key_2": "resource_group_tag_value_2"}
            )
            tags = await client.get_tags(Arn=arn)

            await client.untag(Arn=arn, Keys=["resource_group_tag_key"])
            tags_after = await client.get_tags(Arn=arn)

    assert "resource_group_tag_value_2" in tags["Tags"]["resource_group_tag_key_2"]
    assert tags_after["Tags"] == {
        "resource_group_tag_key_2": "resource_group_tag_value_2"
    }


@pytest.mark.asyncio
async def test_update_group_async() -> None:
    with mock_aws():
        async with _client() as client:
            await _create_group(client)
            updated = await client.update_group(
                GroupName="test_resource_group", Description="description_2"
            )
            fetched = await client.get_group(GroupName="test_resource_group")

    assert updated["Group"]["Description"] == "description_2"
    assert fetched["Group"]["Description"] == "description_2"
