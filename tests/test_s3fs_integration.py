from __future__ import annotations

import asyncio

import pytest

from aiomoto import mock_aws


@pytest.mark.asyncio
async def test_s3fs_reads_and_closes_body() -> None:
    import aiobotocore.session
    import s3fs  # type: ignore[import-untyped]

    with mock_aws():
        session = aiobotocore.session.AioSession()
        fs = s3fs.S3FileSystem(
            anon=False,
            asynchronous=True,
            session=session,
            loop=asyncio.get_running_loop(),
        )
        await fs._connect()

        await fs._call_s3("create_bucket", Bucket="bucket-123")
        path = "bucket-123/test.txt"

        await fs._call_s3(
            "put_object", Bucket="bucket-123", Key="test.txt", Body=b"hello\n"
        )

        assert await fs._cat_file(path) == b"hello\n"

        await fs._s3.close()
