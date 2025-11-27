import re
from typing import Any, TYPE_CHECKING

import aioboto3
import pytest

from aiomoto import mock_aws


if TYPE_CHECKING:
    from aioboto3.client import ClientCreatorContext


TEST_REGION = "us-east-1"
FAKE_SUBNET_ID = "subnet-012345678"
FAKE_SECURITY_GROUP_IDS = ["sg-0123456789abcdef0"]


def _client() -> ClientCreatorContext[Any]:
    return aioboto3.Session().client("fsx", region_name=TEST_REGION)


@pytest.mark.asyncio
async def test_create_and_describe_filesystems_async() -> None:
    with mock_aws():
        async with _client() as client:
            await client.create_file_system(
                FileSystemType="LUSTRE",
                StorageCapacity=1200,
                StorageType="SSD",
                SubnetIds=[FAKE_SUBNET_ID],
                SecurityGroupIds=FAKE_SECURITY_GROUP_IDS,
            )
            await client.create_file_system(
                FileSystemType="WINDOWS",
                StorageCapacity=1200,
                StorageType="SSD",
                SubnetIds=[FAKE_SUBNET_ID],
                SecurityGroupIds=FAKE_SECURITY_GROUP_IDS,
            )

            resp = await client.describe_file_systems()

    file_systems = resp["FileSystems"]
    assert {fs["FileSystemType"] for fs in file_systems} == {"LUSTRE", "WINDOWS"}
    assert all(
        re.match(r"^fs-[0-9a-f]{8,}$", fs["FileSystemId"]) for fs in file_systems
    )


@pytest.mark.asyncio
async def test_create_backup_async() -> None:
    with mock_aws():
        async with _client() as client:
            fs = await client.create_file_system(
                FileSystemType="LUSTRE",
                StorageCapacity=1200,
                StorageType="SSD",
                SubnetIds=[FAKE_SUBNET_ID],
                SecurityGroupIds=FAKE_SECURITY_GROUP_IDS,
            )

            backup = await client.create_backup(
                FileSystemId=fs["FileSystem"]["FileSystemId"],
                Tags=[{"Key": "Moto", "Value": "Hello"}],
            )

    assert backup["Backup"]["BackupId"].startswith("backup-")
