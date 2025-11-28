from __future__ import annotations

import json
from typing import Any, TYPE_CHECKING

import aioboto3
from botocore.exceptions import ClientError
import pytest

from aiomoto import mock_aws


if TYPE_CHECKING:
    from aioboto3.client import ClientCreatorContext


def _client(region: str) -> ClientCreatorContext[Any]:
    return aioboto3.Session().client("personalize", region_name=region)


@pytest.mark.asyncio
async def test_create_and_delete_schema_async() -> None:
    schema_def = {
        "type": "record",
        "name": "Interactions",
        "fields": [
            {"name": "USER_ID", "type": "string"},
            {"name": "ITEM_ID", "type": "string"},
            {"name": "TIMESTAMP", "type": "long"},
        ],
        "version": "1.0",
    }

    with mock_aws():
        async with _client("ap-southeast-1") as client:
            schema_arn = (
                await client.create_schema(
                    name="personalize-demo-schema", schema=json.dumps(schema_def)
                )
            )["schemaArn"]

            await client.delete_schema(schemaArn=schema_arn)

    assert r"schema/personalize-demo-schema" in schema_arn


@pytest.mark.asyncio
async def test_describe_schema_async() -> None:
    with mock_aws():
        async with _client("us-east-2") as client:
            schema_arn = (await client.create_schema(name="myname", schema="sth"))[
                "schemaArn"
            ]
            resp = await client.describe_schema(schemaArn=schema_arn)

    assert resp["schema"]["name"] == "myname"
    assert "schema/myname" in resp["schema"]["schemaArn"]


@pytest.mark.asyncio
async def test_delete_unknown_schema_async() -> None:
    arn = "arn:aws:personalize:ap-southeast-1:123456789012:schema/unknown"
    with mock_aws():
        async with _client("us-east-2") as client:
            with pytest.raises(ClientError) as exc:  # pragma: no branch
                await client.delete_schema(schemaArn=arn)

    err = exc.value.response["Error"]
    assert err["Code"] == "ResourceNotFoundException"
