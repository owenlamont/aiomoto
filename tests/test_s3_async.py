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
            bucket = s3_res_async.Bucket("res-async")
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


@pytest.mark.asyncio
async def test_async_client_empty_object_visible_to_boto3() -> None:
    with mock_aws():
        s3_sync = boto3.client("s3", region_name=AWS_REGION)
        s3_sync.create_bucket(Bucket="async-bucket")

        session = AioSession()
        async with session.create_client("s3", region_name=AWS_REGION) as s3_async:
            await s3_async.put_object(Bucket="async-bucket", Key="empty-key", Body=b"")
            resp = await s3_async.get_object(Bucket="async-bucket", Key="empty-key")
            assert resp["ContentLength"] == 0
            assert await resp["Body"].read() == b""

        sync_resp = s3_sync.get_object(Bucket="async-bucket", Key="empty-key")
        assert sync_resp["ContentLength"] == 0
        assert sync_resp["Body"].read() == b""


@pytest.mark.asyncio
async def test_async_overwrite_and_metadata_shared() -> None:
    with mock_aws():
        s3_sync = boto3.client("s3", region_name=AWS_REGION)
        s3_sync.create_bucket(Bucket="meta-bucket")

        session = AioSession()
        async with session.create_client("s3", region_name=AWS_REGION) as s3_async:
            await s3_async.put_object(
                Bucket="meta-bucket",
                Key="the-key",
                Body=b"first",
                Metadata={"md": "one"},
            )
            initial = await s3_async.get_object(Bucket="meta-bucket", Key="the-key")
            assert initial["ContentLength"] == 5
            assert await initial["Body"].read() == b"first"
            assert initial["Metadata"] == {"md": "one"}

            await s3_async.put_object(Bucket="meta-bucket", Key="the-key", Body=b"")
            updated = await s3_async.get_object(Bucket="meta-bucket", Key="the-key")
            assert updated["ContentLength"] == 0
            assert await updated["Body"].read() == b""

        sync_resp = s3_sync.get_object(Bucket="meta-bucket", Key="the-key")
        assert sync_resp["ContentLength"] == 0
        assert sync_resp["Body"].read() == b""


@pytest.mark.asyncio
async def test_sync_put_visible_to_async_clients_and_resources() -> None:
    with mock_aws():
        s3_sync = boto3.client("s3", region_name=AWS_REGION)
        s3_sync.create_bucket(Bucket="sync-to-async")
        s3_sync.put_object(
            Bucket="sync-to-async", Key="hello.txt", Body=b"sync-wrote-this"
        )

        session = AioSession()
        async with session.create_client("s3", region_name=AWS_REGION) as s3_async:
            resp = await s3_async.get_object(Bucket="sync-to-async", Key="hello.txt")
            assert await resp["Body"].read() == b"sync-wrote-this"

        async with aioboto3.Session().resource(
            "s3", region_name=AWS_REGION
        ) as s3_res_async:
            obj = s3_res_async.Object("sync-to-async", "hello.txt")
            fetched = await obj.get()
            assert await fetched["Body"].read() == b"sync-wrote-this"


@pytest.mark.asyncio
async def test_resource_streaming_body_iteration() -> None:
    with mock_aws():
        s3_sync = boto3.client("s3", region_name=AWS_REGION)
        s3_sync.create_bucket(Bucket="stream-bucket")

        async with aioboto3.Session().resource(
            "s3", region_name=AWS_REGION
        ) as s3_resource:
            obj = s3_resource.Object("stream-bucket", "stream-key")
            await obj.put(Body=b"chunk-onechunk-two")

            resp = await obj.get()
            body = resp["Body"]
            assert resp["ContentLength"] == len("chunk-onechunk-two")

            chunks = [part async for part in body.iter_chunks(chunk_size=5)]
            assert b"".join(chunks) == b"chunk-onechunk-two"

        sync_resp = s3_sync.get_object(Bucket="stream-bucket", Key="stream-key")
        assert sync_resp["Body"].read() == b"chunk-onechunk-two"


@pytest.mark.asyncio
async def test_async_client_listing_preserves_key_names() -> None:
    with mock_aws():
        s3_sync = boto3.client("s3", region_name=AWS_REGION)
        s3_sync.create_bucket(Bucket="list-bucket")

        odd_key = "6T7\x159\x12\r\x08.txt"

        session = AioSession()
        async with session.create_client("s3", region_name=AWS_REGION) as s3_async:
            await s3_async.put_object(Bucket="list-bucket", Key=odd_key, Body=b"")

            resp = await s3_async.list_objects(Bucket="list-bucket")
            assert resp["Contents"][0]["Key"] == odd_key

            resp_v2 = await s3_async.list_objects_v2(Bucket="list-bucket")
            assert resp_v2["Contents"][0]["Key"] == odd_key

        # boto3 should see the same object name to confirm shared Moto state
        sync_key = s3_sync.list_objects(Bucket="list-bucket")["Contents"][0]["Key"]
        assert sync_key == odd_key


@pytest.mark.asyncio
async def test_async_listing_with_prefix_and_encoding_type() -> None:
    with mock_aws():
        s3_sync = boto3.client("s3", region_name=AWS_REGION)
        s3_sync.create_bucket(Bucket="prefix-bucket")

        name = "example/file.text"

        async with aioboto3.Session().resource(
            "s3", region_name=AWS_REGION
        ) as s3_res_async:
            obj = s3_res_async.Object("prefix-bucket", name)
            await obj.put(Body=b"")

        session = AioSession()
        async with session.create_client("s3", region_name=AWS_REGION) as s3_async:
            resp = await s3_async.list_objects(
                Bucket="prefix-bucket",
                Prefix="example/",
                Delimiter="/",
                MaxKeys=1,
                EncodingType="url",
            )

        assert resp["EncodingType"] == "url"
        assert resp["Contents"][0]["Key"] == name

        # boto3 client should see the same key name
        sync_key = s3_sync.list_objects(Bucket="prefix-bucket")["Contents"][0]["Key"]
        assert sync_key == name
