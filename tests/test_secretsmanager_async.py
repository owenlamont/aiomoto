import aioboto3
from aiobotocore.session import AioSession
import boto3
from botocore.exceptions import ClientError
import pytest

from aiomoto import mock_aws


AWS_REGION = "us-east-1"


@pytest.mark.asyncio
async def test_async_client_create_visible_to_boto3() -> None:
    with mock_aws():
        sync = boto3.client("secretsmanager", region_name=AWS_REGION)

        async with AioSession().create_client(
            "secretsmanager", region_name=AWS_REGION
        ) as sm_async:
            await sm_async.create_secret(Name="async-secret", SecretString="hello")
            value = await sm_async.get_secret_value(SecretId="async-secret")
            assert value["SecretString"] == "hello"

        sync_value = sync.get_secret_value(SecretId="async-secret")
        assert sync_value["SecretString"] == "hello"


@pytest.mark.asyncio
async def test_sync_create_visible_to_aioboto3_and_delete() -> None:
    with mock_aws():
        sync = boto3.client("secretsmanager", region_name=AWS_REGION)
        sync.create_secret(Name="sync-secret", SecretBinary=b"binary")

        async with aioboto3.Session().client(
            "secretsmanager", region_name=AWS_REGION
        ) as sm_async:
            value = await sm_async.get_secret_value(SecretId="sync-secret")
            assert value["SecretBinary"] == b"binary"

            await sm_async.delete_secret(
                SecretId="sync-secret", ForceDeleteWithoutRecovery=True
            )

        with pytest.raises(ClientError) as exc:
            sync.get_secret_value(SecretId="sync-secret")
        assert exc.value.response["Error"]["Code"] == "ResourceNotFoundException"


@pytest.mark.asyncio
async def test_async_listing_includes_created_secret() -> None:
    with mock_aws():
        async with AioSession().create_client(
            "secretsmanager", region_name=AWS_REGION
        ) as sm_async:
            await sm_async.create_secret(Name="first", SecretString="one")
            await sm_async.create_secret(Name="second", SecretString="two")

            listed = await sm_async.list_secrets()
            names = {secret["Name"] for secret in listed["SecretList"]}

        assert {"first", "second"}.issubset(names)


@pytest.mark.asyncio
async def test_missing_secret_raises_client_error() -> None:
    with mock_aws():
        async with AioSession().create_client(
            "secretsmanager", region_name=AWS_REGION
        ) as sm_async:
            with pytest.raises(ClientError) as exc:
                await sm_async.get_secret_value(SecretId="absent")

        error = exc.value.response["Error"]
        assert error["Code"] == "ResourceNotFoundException"


@pytest.mark.asyncio
async def test_secrets_backend_isolated_by_region() -> None:
    with mock_aws():
        boto3.client("secretsmanager", region_name=AWS_REGION).create_secret(
            Name="regional", SecretString="east"
        )

        async with AioSession().create_client(
            "secretsmanager", region_name="us-west-2"
        ) as sm_west:
            with pytest.raises(ClientError) as exc:
                await sm_west.get_secret_value(SecretId="regional")

        assert exc.value.response["Error"]["Code"] == "ResourceNotFoundException"
