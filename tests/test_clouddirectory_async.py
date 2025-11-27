from typing import Any, TYPE_CHECKING

import aioboto3
from moto.core import DEFAULT_ACCOUNT_ID  # type: ignore[attr-defined]
import pytest

from aiomoto import mock_aws


if TYPE_CHECKING:
    from aioboto3.client import ClientCreatorContext


def _client(region: str = "us-west-2") -> ClientCreatorContext[Any]:
    return aioboto3.Session().client("clouddirectory", region_name=region)


@pytest.mark.asyncio
async def test_create_directory_async() -> None:
    with mock_aws():
        async with _client() as client:
            schema = await client.create_schema(Name="test-schema")
            schema_arn = schema["SchemaArn"]
            resp = await client.create_directory(
                SchemaArn=schema_arn, Name="test-directory"
            )

    assert resp["DirectoryArn"] == (
        f"arn:aws:clouddirectory:us-west-2:{DEFAULT_ACCOUNT_ID}:directory/test-directory"
    )
    assert resp["AppliedSchemaArn"] == schema_arn


@pytest.mark.asyncio
async def test_apply_schema_async() -> None:
    with mock_aws():
        async with _client() as client:
            schema = await client.create_schema(Name="test-schema")
            dev_arn = schema["SchemaArn"]
            pub = await client.publish_schema(
                DevelopmentSchemaArn=dev_arn, Name="test-schema", Version="1"
            )
            pub_arn = pub["PublishedSchemaArn"]
            directory = await client.create_directory(
                SchemaArn=pub_arn, Name="test-directory"
            )
            resp = await client.apply_schema(
                PublishedSchemaArn=pub_arn, DirectoryArn=directory["DirectoryArn"]
            )

    assert resp["AppliedSchemaArn"] == pub_arn


@pytest.mark.asyncio
async def test_list_directories_async() -> None:
    with mock_aws():
        async with _client() as client:
            schema_arn = (
                "arn:aws:clouddirectory:"
                f"us-west-2:{DEFAULT_ACCOUNT_ID}:directory/test-schema/1"
            )
            for i in range(3):
                await client.create_directory(
                    SchemaArn=schema_arn, Name=f"test-directory-{i}"
                )

            resp = await client.list_directories()
            paged = await client.list_directories(MaxResults=1)
            filtered = await client.list_directories(state="ENABLED")

    assert len(resp["Directories"]) == 3
    assert "NextToken" in paged
    assert len(filtered["Directories"]) == 3


@pytest.mark.asyncio
async def test_tag_and_untag_resource_async() -> None:
    with mock_aws():
        async with _client("us-east-2") as client:
            schema_arn = (
                "arn:aws:clouddirectory:"
                f"us-east-2:{DEFAULT_ACCOUNT_ID}:directory/test-schema/1"
            )
            directory_arn = (
                await client.create_directory(
                    SchemaArn=schema_arn, Name="test-directory"
                )
            )["DirectoryArn"]
            await client.tag_resource(
                ResourceArn=directory_arn, Tags=[{"Key": "key1", "Value": "value1"}]
            )
            await client.tag_resource(
                ResourceArn=directory_arn, Tags=[{"Key": "key2", "Value": "value2"}]
            )
            tags = await client.list_tags_for_resource(ResourceArn=directory_arn)
            await client.untag_resource(
                ResourceArn=directory_arn, TagKeys=["key1", "key2"]
            )
            tags_after = await client.list_tags_for_resource(ResourceArn=directory_arn)

    assert len(tags["Tags"]) == 2
    assert tags_after["Tags"] == []
