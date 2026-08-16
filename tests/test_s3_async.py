from __future__ import annotations

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
async def test_sync_put_visible_to_async_clients() -> None:
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


@pytest.mark.asyncio
async def test_async_client_streaming_body_iteration() -> None:
    with mock_aws():
        s3_sync = boto3.client("s3", region_name=AWS_REGION)
        s3_sync.create_bucket(Bucket="stream-bucket")

        async with AioSession().create_client("s3", region_name=AWS_REGION) as s3_async:
            await s3_async.put_object(
                Bucket="stream-bucket", Key="stream-key", Body=b"chunk-onechunk-two"
            )

            resp = await s3_async.get_object(Bucket="stream-bucket", Key="stream-key")
            body = resp["Body"]
            assert resp["ContentLength"] == len("chunk-onechunk-two")

            chunks = [part async for part in body.iter_chunks(chunk_size=5)]
            assert b"".join(chunks) == b"chunk-onechunk-two"

        sync_resp = s3_sync.get_object(Bucket="stream-bucket", Key="stream-key")
        assert sync_resp["Body"].read() == b"chunk-onechunk-two"


@pytest.mark.asyncio
async def test_streaming_body_context_manager_supports_sized_read() -> None:
    with mock_aws():
        s3_sync = boto3.client("s3", region_name=AWS_REGION)
        s3_sync.create_bucket(Bucket="ctx-bucket")

        async with AioSession().create_client("s3", region_name=AWS_REGION) as s3_async:
            await s3_async.put_object(
                Bucket="ctx-bucket", Key="ctx-key", Body=b"y" * 4096
            )

            resp = await s3_async.get_object(Bucket="ctx-bucket", Key="ctx-key")
            body = resp["Body"]
            async with body as stream:
                assert stream is body
                assert await stream.read(1024) == b"y" * 1024
                assert await stream.read() == b"y" * 3072

            resp = await s3_async.get_object(Bucket="ctx-bucket", Key="ctx-key")
            async with resp["Body"] as stream:
                partial = await stream.raw_stream.content.read(1024)
            assert partial == b"y" * 1024

            resp = await s3_async.get_object(Bucket="ctx-bucket", Key="ctx-key")
            async with resp["Body"] as stream:
                full = await stream.read()
            assert full == b"y" * 4096


@pytest.mark.asyncio
async def test_object_state_persists_across_repeated_reads() -> None:
    with mock_aws():
        async with AioSession().create_client("s3", region_name=AWS_REGION) as s3_async:
            await s3_async.create_bucket(Bucket="persist-bucket")
            await s3_async.put_object(
                Bucket="persist-bucket", Key="persist-key", Body=b"hello world"
            )

            first = await s3_async.get_object(
                Bucket="persist-bucket", Key="persist-key"
            )
            assert await first["Body"].read() == b"hello world"

            second = await s3_async.get_object(
                Bucket="persist-bucket", Key="persist-key"
            )
            assert await second["Body"].read() == b"hello world"

            partial = await s3_async.get_object(
                Bucket="persist-bucket", Key="persist-key"
            )
            body = partial["Body"]
            assert await body.read(5) == b"hello"
            assert await body.read(6) == b" world"
            assert await body.read(1) == b""


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

        session = AioSession()
        async with session.create_client("s3", region_name=AWS_REGION) as s3_async:
            await s3_async.put_object(Bucket="prefix-bucket", Key=name, Body=b"")

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
