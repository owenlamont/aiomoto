from __future__ import annotations

import boto3
import pytest

from aiomoto import mock_aws


pytest.importorskip("flask")
pytest.importorskip("flask_cors")
pl = pytest.importorskip("polars")
assert_frame_equal = pytest.importorskip("polars.testing").assert_frame_equal


def _create_bucket(bucket: str) -> None:
    client = boto3.client("s3")
    client.create_bucket(Bucket=bucket)


@pytest.mark.parametrize(
    ("extension", "write_method", "read_func", "scan_func"),
    [
        ("parquet", "write_parquet", "read_parquet", "scan_parquet"),
        ("csv", "write_csv", "read_csv", "scan_csv"),
        ("ipc", "write_ipc", "read_ipc", "scan_ipc"),
        ("ndjson", "write_ndjson", "read_ndjson", "scan_ndjson"),
    ],
    ids=("parquet", "csv", "ipc", "ndjson"),
)
def test_polars_server_mode_roundtrip(
    extension: str, write_method: str, read_func: str, scan_func: str
) -> None:
    df = pl.DataFrame({"a": [1, 2], "b": ["x", "y"]})
    bucket = f"bucket-polars-{extension}"
    path = f"s3://{bucket}/data.{extension}"

    with mock_aws(server_mode=True):
        _create_bucket(bucket)
        getattr(df, write_method)(path)
        read_df = getattr(pl, read_func)(path)
        assert_frame_equal(read_df, df)
        scan_df = getattr(pl, scan_func)(path).collect()
        assert_frame_equal(scan_df, df)
        if extension == "parquet":
            metadata = pl.read_parquet_metadata(path)
            assert "ARROW:schema" in metadata


@pytest.mark.parametrize(
    ("extension", "sink_method", "read_func"),
    [
        ("parquet", "sink_parquet", "read_parquet"),
        ("csv", "sink_csv", "read_csv"),
        ("ipc", "sink_ipc", "read_ipc"),
        ("ndjson", "sink_ndjson", "read_ndjson"),
    ],
    ids=("parquet", "csv", "ipc", "ndjson"),
)
def test_polars_server_mode_lazy_sink_roundtrip(
    extension: str, sink_method: str, read_func: str
) -> None:
    df = pl.DataFrame({"a": [1, 2], "b": ["x", "y"]})
    bucket = f"bucket-polars-sink-{extension}"
    path = f"s3://{bucket}/data.{extension}"

    with mock_aws(server_mode=True):
        _create_bucket(bucket)
        getattr(df.lazy(), sink_method)(path)
        read_df = getattr(pl, read_func)(path)
        assert_frame_equal(read_df, df)
