from __future__ import annotations

from aiomoto import mock_aws


def test_s3fs_reads_and_closes_body() -> None:
    import boto3
    import s3fs  # type: ignore[import-untyped]

    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket="bucket-123")

        fs = s3fs.S3FileSystem()
        path = "s3://bucket-123/test.txt"

        with fs.open(path, "wb") as writable:
            writable.write(b"hello\n")

        with fs.open(path, "rb") as readable:
            assert readable.read() == b"hello\n"
