from typing import Any, TYPE_CHECKING

import aioboto3
from botocore.exceptions import ClientError
import pytest

from aiomoto import mock_aws


if TYPE_CHECKING:
    from aioboto3.client import ClientCreatorContext


def _client() -> ClientCreatorContext[Any]:
    return aioboto3.Session().client("datasync", region_name="us-east-1")


async def _create_locations(client: Any) -> tuple[str, str]:
    smb_arn = (
        await client.create_location_smb(
            ServerHostname="host",
            Subdirectory="somewhere",
            User="user",
            Password="",
            AgentArns=["agent"],
        )
    )["LocationArn"]
    s3_arn = (
        await client.create_location_s3(
            S3BucketArn="arn:aws:s3:::my_bucket",
            Subdirectory="dir",
            S3Config={"BucketAccessRoleArn": "role"},
        )
    )["LocationArn"]
    return smb_arn, s3_arn


@pytest.mark.asyncio
async def test_location_crud_async() -> None:
    with mock_aws():
        async with _client() as client:
            smb_arn, _ = await _create_locations(client)

            desc = await client.describe_location_smb(LocationArn=smb_arn)
            assert desc["LocationArn"] == smb_arn
            assert desc["User"] == "user"

            listed = await client.list_locations()
            assert len(listed["Locations"]) == 2

            await client.delete_location(LocationArn=smb_arn)
            remaining = await client.list_locations()
            assert len(remaining["Locations"]) == 1

            with pytest.raises(ClientError):  # pragma: no branch
                await client.delete_location(LocationArn=smb_arn)


@pytest.mark.asyncio
async def test_task_create_and_list_async() -> None:
    with mock_aws():
        async with _client() as client:
            smb_arn, s3_arn = await _create_locations(client)

            task1 = await client.create_task(
                SourceLocationArn=smb_arn, DestinationLocationArn=s3_arn
            )
            task2 = await client.create_task(
                SourceLocationArn=s3_arn,
                DestinationLocationArn=smb_arn,
                Name="roundtrip",
            )

            tasks = (await client.list_tasks())["Tasks"]
            assert {t["TaskArn"] for t in tasks} == {task1["TaskArn"], task2["TaskArn"]}
            assert any(t.get("Name") == "roundtrip" for t in tasks)

            desc = await client.describe_task(TaskArn=task1["TaskArn"])
            assert desc["Status"] == "AVAILABLE"


@pytest.mark.asyncio
async def test_task_create_requires_locations_async() -> None:
    with mock_aws():
        async with _client() as client:
            _, s3_arn = await _create_locations(client)

            with pytest.raises(ClientError) as exc:  # pragma: no branch
                await client.create_task(
                    SourceLocationArn="missing", DestinationLocationArn=s3_arn
                )

    err = exc.value.response["Error"]
    assert err["Code"] == "InvalidRequestException"
    assert err["Message"] == "Location missing not found."
