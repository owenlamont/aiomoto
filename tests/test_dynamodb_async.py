from __future__ import annotations

import aioboto3
from aiobotocore.session import AioSession
import boto3
from botocore.exceptions import ClientError
import pytest

from aiomoto import mock_aws


AWS_REGION = "us-west-2"


@pytest.mark.asyncio
async def test_client_create_describe_and_crud_shared_with_boto3() -> None:
    with mock_aws():
        async with AioSession().create_client(
            "dynamodb", region_name=AWS_REGION
        ) as dynamodb:
            await dynamodb.create_table(
                TableName="items",
                KeySchema=[{"AttributeName": "pk", "KeyType": "HASH"}],
                AttributeDefinitions=[{"AttributeName": "pk", "AttributeType": "S"}],
                BillingMode="PAY_PER_REQUEST",
            )
            desc = await dynamodb.describe_table(TableName="items")
            assert desc["Table"]["TableStatus"] == "ACTIVE"

            await dynamodb.put_item(TableName="items", Item={"pk": {"S": "one"}})
            found = await dynamodb.get_item(TableName="items", Key={"pk": {"S": "one"}})
            assert found["Item"]["pk"]["S"] == "one"

            with pytest.raises(ClientError) as exc:
                await dynamodb.get_item(
                    TableName="missing", Key={"pk": {"S": "absent"}}
                )
            assert exc.value.response["Error"]["Code"] == "ResourceNotFoundException"

        sync = boto3.client("dynamodb", region_name=AWS_REGION)
        sync_desc = sync.describe_table(TableName="items")["Table"]
        assert sync_desc["KeySchema"] == [{"AttributeName": "pk", "KeyType": "HASH"}]
        sync_item = sync.get_item(TableName="items", Key={"pk": {"S": "one"}})
        assert sync_item["Item"]["pk"]["S"] == "one"


@pytest.mark.asyncio
async def test_dynamodb_backend_isolated_by_region() -> None:
    with mock_aws():
        boto3.client("dynamodb", region_name="us-east-1").create_table(
            TableName="regional",
            KeySchema=[{"AttributeName": "pk", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "pk", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )

        async with AioSession().create_client(
            "dynamodb", region_name=AWS_REGION
        ) as dynamodb:
            with pytest.raises(ClientError) as exc:
                await dynamodb.describe_table(TableName="regional")

        assert exc.value.response["Error"]["Code"] == "ResourceNotFoundException"


@pytest.mark.asyncio
async def test_aioboto3_resource_supports_sort_keys_and_indexes() -> None:
    with mock_aws():
        async with aioboto3.Session().resource(
            "dynamodb", region_name=AWS_REGION
        ) as dynamodb:
            table = await dynamodb.create_table(
                TableName="complex",
                KeySchema=[
                    {"AttributeName": "pk", "KeyType": "HASH"},
                    {"AttributeName": "sk", "KeyType": "RANGE"},
                ],
                AttributeDefinitions=[
                    {"AttributeName": "pk", "AttributeType": "S"},
                    {"AttributeName": "sk", "AttributeType": "S"},
                    {"AttributeName": "lsi_sk", "AttributeType": "S"},
                    {"AttributeName": "gsi_pk", "AttributeType": "S"},
                ],
                LocalSecondaryIndexes=[
                    {
                        "IndexName": "lsi1",
                        "KeySchema": [
                            {"AttributeName": "pk", "KeyType": "HASH"},
                            {"AttributeName": "lsi_sk", "KeyType": "RANGE"},
                        ],
                        "Projection": {"ProjectionType": "ALL"},
                    }
                ],
                GlobalSecondaryIndexes=[
                    {
                        "IndexName": "gsi1",
                        "KeySchema": [
                            {"AttributeName": "gsi_pk", "KeyType": "HASH"},
                            {"AttributeName": "sk", "KeyType": "RANGE"},
                        ],
                        "Projection": {"ProjectionType": "ALL"},
                        "ProvisionedThroughput": {
                            "ReadCapacityUnits": 5,
                            "WriteCapacityUnits": 5,
                        },
                    }
                ],
                ProvisionedThroughput={"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
            )
            await table.put_item(
                Item={
                    "pk": {"S": "parent"},
                    "sk": {"S": "0001"},
                    "lsi_sk": {"S": "alt"},
                    "gsi_pk": {"S": "g-1"},
                    "payload": {"S": "v1"},
                }
            )
            item = await table.get_item(
                Key={"pk": {"S": "parent"}, "sk": {"S": "0001"}}
            )
            assert item["Item"]["payload"]["S"] == "v1"

        sync = boto3.client("dynamodb", region_name=AWS_REGION)
        desc = sync.describe_table(TableName="complex")["Table"]
        assert {idx["IndexName"] for idx in desc["LocalSecondaryIndexes"]} == {"lsi1"}
        assert {idx["IndexName"] for idx in desc["GlobalSecondaryIndexes"]} == {"gsi1"}
        sync_item = sync.get_item(
            TableName="complex", Key={"pk": {"S": "parent"}, "sk": {"S": "0001"}}
        )
        assert sync_item["Item"]["gsi_pk"]["S"] == "g-1"


@pytest.mark.asyncio
async def test_sync_put_visible_to_async_client() -> None:
    with mock_aws():
        sync = boto3.client("dynamodb", region_name=AWS_REGION)
        sync.create_table(
            TableName="bridge",
            KeySchema=[{"AttributeName": "pk", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "pk", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        sync.put_item(TableName="bridge", Item={"pk": {"S": "from-sync"}})

        async with AioSession().create_client(
            "dynamodb", region_name=AWS_REGION
        ) as dynamodb:
            item = await dynamodb.get_item(
                TableName="bridge", Key={"pk": {"S": "from-sync"}}
            )
            assert item["Item"]["pk"]["S"] == "from-sync"


@pytest.mark.asyncio
async def test_sync_put_visible_to_async_resource() -> None:
    with mock_aws():
        sync = boto3.client("dynamodb", region_name=AWS_REGION)
        sync.create_table(
            TableName="bridge-res",
            KeySchema=[{"AttributeName": "pk", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "pk", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        sync.put_item(TableName="bridge-res", Item={"pk": {"S": "sync-val"}})

        async with aioboto3.Session().resource(
            "dynamodb", region_name=AWS_REGION
        ) as dynamodb:
            table = dynamodb.Table("bridge-res")
            item = await table.get_item(Key={"pk": {"S": "sync-val"}})
            assert item["Item"]["pk"]["S"] == "sync-val"
