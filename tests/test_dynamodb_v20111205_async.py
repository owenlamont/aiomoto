from __future__ import annotations

from typing import Any, TYPE_CHECKING

import aioboto3
import pytest

from aiomoto import mock_aws


if TYPE_CHECKING:
    from aioboto3.client import ClientCreatorContext


def _client(region: str = "us-west-2") -> ClientCreatorContext[Any]:
    return aioboto3.Session().client("dynamodb", region_name=region)


@pytest.mark.asyncio
async def test_create_list_delete_table_v20111205_async() -> None:
    with mock_aws():
        async with _client() as client:
            await client.create_table(
                TableName="Thread",
                KeySchema=[{"AttributeName": "ForumName", "KeyType": "HASH"}],
                AttributeDefinitions=[
                    {"AttributeName": "ForumName", "AttributeType": "S"}
                ],
                ProvisionedThroughput={"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
            )
            tables = await client.list_tables()
            await client.delete_table(TableName="Thread")

    assert "Thread" in tables["TableNames"]


@pytest.mark.asyncio
async def test_put_and_get_item_async() -> None:
    with mock_aws():
        async with _client() as client:
            await client.create_table(
                TableName="Thread",
                KeySchema=[{"AttributeName": "ForumName", "KeyType": "HASH"}],
                AttributeDefinitions=[
                    {"AttributeName": "ForumName", "AttributeType": "S"}
                ],
                ProvisionedThroughput={"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
            )
            await client.put_item(
                TableName="Thread",
                Item={"ForumName": {"S": "LOLCat Forum"}, "Threads": {"N": "0"}},
            )
            item = await client.get_item(
                TableName="Thread", Key={"ForumName": {"S": "LOLCat Forum"}}
            )

    assert item["Item"]["Threads"]["N"] == "0"
