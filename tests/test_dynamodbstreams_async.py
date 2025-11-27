from typing import Any, TYPE_CHECKING

import aioboto3
import pytest

from aiomoto import mock_aws


if TYPE_CHECKING:
    from aioboto3.client import ClientCreatorContext


def _ddb() -> ClientCreatorContext[Any]:
    return aioboto3.Session().client("dynamodb", region_name="us-east-1")


def _streams() -> ClientCreatorContext[Any]:
    return aioboto3.Session().client("dynamodbstreams", region_name="us-east-1")


@pytest.mark.asyncio
async def test_list_streams_async() -> None:
    with mock_aws():
        async with _ddb() as ddb:
            await ddb.create_table(
                TableName="tbl",
                KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
                AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
                BillingMode="PAY_PER_REQUEST",
                StreamSpecification={
                    "StreamEnabled": True,
                    "StreamViewType": "NEW_IMAGE",
                },
            )

        async with _streams() as streams:
            resp = await streams.list_streams(TableName="tbl")

    assert len(resp.get("Streams", [])) == 1
