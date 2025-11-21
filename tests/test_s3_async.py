import aioboto3
from aiobotocore.session import AioSession
import boto3
from botocore.exceptions import ClientError
import pytest

from aiomoto import mock_aws


AWS_REGION = "us-east-1"


@pytest.mark.asyncio
async def test_bucket_visibility_between_sync_and_async_clients() -> None:
    with mock_aws():
        s3_sync = boto3.client("s3", region_name=AWS_REGION)
        s3_sync.create_bucket(Bucket="mybucket")

        session = AioSession()
        async with session.create_client("s3", region_name=AWS_REGION) as s3_async:
            response = await s3_async.list_buckets()
            bucket_names = [bucket["Name"] for bucket in response["Buckets"]]
            assert "mybucket" in bucket_names

        async with session.create_client("s3", region_name=AWS_REGION) as s3_async:
            await s3_async.create_bucket(Bucket="async-bucket")

        bucket_names_sync = [
            bucket["Name"] for bucket in s3_sync.list_buckets()["Buckets"]
        ]
        assert "async-bucket" in bucket_names_sync


@pytest.mark.asyncio
async def test_sync_boto3_to_async_aioboto3_visibility() -> None:
    with mock_aws():
        s3_sync = boto3.client("s3", region_name=AWS_REGION)
        s3_sync.create_bucket(Bucket="sync-bucket")

        async with aioboto3.Session().client("s3", region_name=AWS_REGION) as s3_async:
            buckets = await s3_async.list_buckets()
            names = [bucket["Name"] for bucket in buckets["Buckets"]]
            assert "sync-bucket" in names

        async with aioboto3.Session().client("s3", region_name=AWS_REGION) as s3_async:
            await s3_async.create_bucket(Bucket="aio-bucket")

        bucket_names_sync = [
            bucket["Name"] for bucket in s3_sync.list_buckets()["Buckets"]
        ]
        assert "aio-bucket" in bucket_names_sync


@pytest.mark.asyncio
@pytest.mark.skip(
    reason=(
        "aioboto3.resource currently expects a sync client; aiomoto does not yet "
        "supply one"
    )
)
async def test_resource_visibility_between_sync_and_async() -> None:
    with mock_aws():
        # sync create via resource
        s3_res_sync = boto3.resource("s3", region_name=AWS_REGION)
        s3_res_sync.create_bucket(Bucket="res-sync")

        async with aioboto3.Session().resource(
            "s3", region_name=AWS_REGION
        ) as s3_res_async:
            names = [bucket.name async for bucket in s3_res_async.buckets.all()]
            assert "res-sync" in names

        # async create via resource
        async with aioboto3.Session().resource(
            "s3", region_name=AWS_REGION
        ) as s3_res_async:
            bucket = await s3_res_async.Bucket("res-async")
            await bucket.create()

        bucket_names_sync = [bucket.name for bucket in s3_res_sync.buckets.all()]
        assert "res-async" in bucket_names_sync


@pytest.mark.asyncio
async def test_missing_bucket_raises_client_error() -> None:
    with mock_aws():
        session = AioSession()
        async with session.create_client("s3", region_name=AWS_REGION) as s3_async:
            with pytest.raises(ClientError) as exc_info:
                await s3_async.get_object(Bucket="missing-bucket", Key="the-key")

        error = exc_info.value.response["Error"]
        assert error["Code"] == "NoSuchBucket"
        assert error["Message"] == "The specified bucket does not exist"
