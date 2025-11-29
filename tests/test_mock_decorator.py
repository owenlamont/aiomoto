from __future__ import annotations

import uuid

from aiobotocore.session import AioSession
import boto3
import pytest

from aiomoto import mock_aws, mock_aws_decorator


def test_sync_decorator_allows_boto3_calls() -> None:
    bucket = f"decorator-sync-{uuid.uuid4().hex}"

    @mock_aws
    def create_and_list(name: str) -> list[str]:
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket=name)
        response = client.list_buckets()
        return [bucket_info["Name"] for bucket_info in response.get("Buckets", [])]

    assert bucket in create_and_list(bucket)


@pytest.mark.asyncio
async def test_async_decorator_allows_aiobotocore_calls() -> None:
    bucket = f"decorator-async-{uuid.uuid4().hex}"

    @mock_aws_decorator()
    async def create_and_list(name: str) -> list[str]:
        session = AioSession()
        async with session.create_client("s3", region_name="us-east-1") as client:
            await client.create_bucket(Bucket=name)
            response = await client.list_buckets()
        return [bucket_info["Name"] for bucket_info in response.get("Buckets", [])]

    assert bucket in await create_and_list(bucket)
