from __future__ import annotations

import sys

import boto3
import pytest

from aiomoto import mock_aws
from aiomoto.patches import server_mode as server_mode_patches


if hasattr(sys, "_is_gil_enabled") and not sys._is_gil_enabled():  # pragma: no cover
    pytest.skip(
        "Polars server-mode integration is not validated on free-threaded builds",
        allow_module_level=True,
    )

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


def test_polars_write_ndjson_without_query_opt_flags(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    df = pl.DataFrame({"a": [1, 2], "b": ["x", "y"]})
    bucket = "bucket-polars-ndjson-no-opt"
    path = f"s3://{bucket}/data.ndjson"

    with mock_aws(server_mode=True):
        _create_bucket(bucket)
        monkeypatch.setattr(
            server_mode_patches, "_polars_query_opt_flags_eager", lambda: None
        )
        df.write_ndjson(path)
        read_df = pl.read_ndjson(path)
        assert_frame_equal(read_df, df)


def test_polars_server_mode_csv_pyarrow_roundtrip() -> None:
    frame = pl.DataFrame({"value": [1, 2]})
    path = "s3://bucket-polars-csv-pyarrow/data.csv"

    with mock_aws(server_mode=True):
        _create_bucket("bucket-polars-csv-pyarrow")
        frame.write_csv(path)
        result = pl.read_csv(path, use_pyarrow=True)

    assert_frame_equal(result, frame)


def test_polars_server_mode_ipc_pyarrow_roundtrip() -> None:
    frame = pl.DataFrame({"value": [1, 2]})
    path = "s3://bucket-polars-ipc-pyarrow/data.ipc"

    with mock_aws(server_mode=True):
        _create_bucket("bucket-polars-ipc-pyarrow")
        frame.write_ipc(path)
        result = pl.read_ipc(path, use_pyarrow=True)

    assert_frame_equal(result, frame)
