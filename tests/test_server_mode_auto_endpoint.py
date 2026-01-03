from __future__ import annotations

from aiobotocore.session import AioSession
import boto3
import pytest

from aiomoto import mock_aws
from aiomoto.patches.server_mode import AutoEndpointMode


pytest.importorskip("flask")
pytest.importorskip("flask_cors")


@pytest.mark.asyncio
async def test_server_mode_auto_endpoint_aiobotocore() -> None:
    with mock_aws(server_mode=True) as ctx:
        endpoint = ctx.server_endpoint
        assert endpoint is not None
        async with AioSession().create_client("s3") as client:
            assert client.meta.endpoint_url == endpoint
            await client.create_bucket(Bucket="aiomoto-async")
            response = await client.list_buckets()
            assert any(b["Name"] == "aiomoto-async" for b in response["Buckets"])


def test_server_mode_auto_endpoint_boto3_force_overrides() -> None:
    with mock_aws(server_mode=True) as ctx:
        endpoint = ctx.server_endpoint
        assert endpoint is not None
        client = boto3.client("s3", endpoint_url="http://example.com")
        assert client.meta.endpoint_url == endpoint
        client.create_bucket(Bucket="aiomoto-sync")
        response = client.list_buckets()
        assert any(b["Name"] == "aiomoto-sync" for b in response["Buckets"])


def test_server_mode_auto_endpoint_if_missing_preserves_endpoint() -> None:
    with mock_aws(server_mode=True, auto_endpoint=AutoEndpointMode.IF_MISSING):
        client = boto3.client("s3", endpoint_url="http://example.com")
        assert client.meta.endpoint_url == "http://example.com"


@pytest.mark.asyncio
async def test_server_mode_auto_endpoint_aioboto3() -> None:
    aioboto3 = pytest.importorskip("aioboto3")
    with mock_aws(server_mode=True) as ctx:
        endpoint = ctx.server_endpoint
        assert endpoint is not None
        session = aioboto3.Session()
        async with session.client("s3") as client:
            assert client.meta.endpoint_url == endpoint
            await client.create_bucket(Bucket="aiomoto-aioboto3")
            response = await client.list_buckets()
            assert any(b["Name"] == "aiomoto-aioboto3" for b in response["Buckets"])


def test_server_mode_auto_endpoint_s3fs() -> None:
    s3fs = pytest.importorskip("s3fs")
    with mock_aws(server_mode=True) as ctx:
        endpoint = ctx.server_endpoint
        assert endpoint is not None
        fs = s3fs.S3FileSystem(asynchronous=False, anon=False)
        assert fs.endpoint_url == endpoint
        assert fs.use_ssl is False
        fs.call_s3("create_bucket", Bucket="aiomoto-s3fs")
        fs.call_s3("put_object", Bucket="aiomoto-s3fs", Key="test.txt", Body=b"hi")
        assert fs.cat("aiomoto-s3fs/test.txt") == b"hi"
