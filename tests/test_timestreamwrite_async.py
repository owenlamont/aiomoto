from __future__ import annotations

from typing import Any, TYPE_CHECKING

import aioboto3
from botocore.exceptions import ClientError
from moto.core import DEFAULT_ACCOUNT_ID as ACCOUNT_ID  # type: ignore[attr-defined]
import pytest

from aiomoto import mock_aws


if TYPE_CHECKING:
    from aioboto3.client import ClientCreatorContext


def _client() -> ClientCreatorContext[Any]:
    return aioboto3.Session().client("timestream-write", region_name="us-east-1")


@pytest.mark.asyncio
async def test_create_database_advanced_async() -> None:
    with mock_aws():
        async with _client() as ts:
            resp = await ts.create_database(
                DatabaseName="mydatabase",
                KmsKeyId="mykey",
                Tags=[{"Key": "k1", "Value": "v1"}, {"Key": "k2", "Value": "v2"}],
            )
            database = resp["Database"]

    assert database["Arn"] == (
        f"arn:aws:timestream:us-east-1:{ACCOUNT_ID}:database/mydatabase"
    )
    assert database["DatabaseName"] == "mydatabase"
    assert database["TableCount"] == 0
    assert database["KmsKeyId"] == "mykey"


@pytest.mark.asyncio
async def test_describe_database_async() -> None:
    with mock_aws():
        async with _client() as ts:
            await ts.create_database(DatabaseName="mydatabase", KmsKeyId="mykey")
            database = (await ts.describe_database(DatabaseName="mydatabase"))[
                "Database"
            ]

    assert database["Arn"] == (
        f"arn:aws:timestream:us-east-1:{ACCOUNT_ID}:database/mydatabase"
    )
    assert database["DatabaseName"] == "mydatabase"
    assert database["TableCount"] == 0
    assert database["KmsKeyId"] == "mykey"


@pytest.mark.asyncio
async def test_describe_unknown_database_async() -> None:
    with mock_aws():
        async with _client() as ts:
            with pytest.raises(ClientError):  # pragma: no branch
                await ts.describe_database(DatabaseName="unknown")


@pytest.mark.asyncio
async def test_list_databases_async() -> None:
    with mock_aws():
        async with _client() as ts:
            await ts.create_database(DatabaseName="db_with", KmsKeyId="mykey")
            await ts.create_database(DatabaseName="db_without")

            resp = await ts.list_databases()
            databases = resp["Databases"]
            for db in databases:
                db.pop("CreationTime")
                db.pop("LastUpdatedTime")

    assert len(databases) == 2
    assert {
        "Arn": f"arn:aws:timestream:us-east-1:{ACCOUNT_ID}:database/db_with",
        "DatabaseName": "db_with",
        "TableCount": 0,
        "KmsKeyId": "mykey",
    } in databases
    assert {
        "Arn": f"arn:aws:timestream:us-east-1:{ACCOUNT_ID}:database/db_without",
        "DatabaseName": "db_without",
        "TableCount": 0,
        "KmsKeyId": f"arn:aws:kms:us-east-1:{ACCOUNT_ID}:key/default_key",
    } in databases


@pytest.mark.asyncio
async def test_delete_database_async() -> None:
    with mock_aws():
        async with _client() as ts:
            await ts.create_database(DatabaseName="db_1", KmsKeyId="mykey")
            await ts.create_database(DatabaseName="db_2")
            await ts.create_database(DatabaseName="db_3", KmsKeyId="mysecondkey")
            assert len((await ts.list_databases())["Databases"]) == 3

            await ts.delete_database(DatabaseName="db_2")
            databases = (await ts.list_databases())["Databases"]

    assert len(databases) == 2
    assert [db["DatabaseName"] for db in databases] == ["db_1", "db_3"]


@pytest.mark.asyncio
async def test_update_database_async() -> None:
    with mock_aws():
        async with _client() as ts:
            await ts.create_database(DatabaseName="mydatabase", KmsKeyId="mykey")
            resp = await ts.update_database(
                DatabaseName="mydatabase", KmsKeyId="updatedkey"
            )
            database = resp["Database"]
            db_desc = (await ts.describe_database(DatabaseName="mydatabase"))[
                "Database"
            ]

    assert database["KmsKeyId"] == "updatedkey"
    assert db_desc["KmsKeyId"] == "updatedkey"
