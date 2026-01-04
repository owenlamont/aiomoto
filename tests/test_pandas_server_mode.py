from __future__ import annotations

import sys

import boto3
import pytest


# Free-threaded CPython (PYTHON_GIL=0 / 3.14t) forces pandas to enable the GIL at
# import time, emitting a RuntimeWarning that is treated as an error in our
# warnings-as-errors config. Skip the module on such interpreters.
if hasattr(sys, "_is_gil_enabled") and not sys._is_gil_enabled():  # pragma: no cover
    pytest.skip(
        "pandas is not yet compatible with free-threaded CPython builds",
        allow_module_level=True,
    )

pytest.importorskip("flask")
pytest.importorskip("flask_cors")
pytest.importorskip("fsspec")
pytest.importorskip("pandas")
pytest.importorskip("s3fs")
pytest.importorskip("pyarrow")

import pandas as pd
import pandas.testing as pdt

from aiomoto import mock_aws


def _create_bucket(bucket: str) -> None:
    client = boto3.client("s3")
    client.create_bucket(Bucket=bucket)


def test_pandas_server_mode_csv_roundtrip() -> None:
    df = pd.DataFrame({"a": [1, 2], "b": ["x", "y"]})
    path = "s3://bucket-pandas-csv/data.csv"

    with mock_aws(server_mode=True):
        _create_bucket("bucket-pandas-csv")
        df.to_csv(path, index=False)
        result = pd.read_csv(path)

    pdt.assert_frame_equal(result, df)


def test_pandas_server_mode_parquet_roundtrip() -> None:
    df = pd.DataFrame({"a": [1, 2], "b": ["x", "y"]})
    path = "s3://bucket-pandas-parquet/data.parquet"

    with mock_aws(server_mode=True):
        _create_bucket("bucket-pandas-parquet")
        df.to_parquet(path)
        result = pd.read_parquet(path)

    pdt.assert_frame_equal(result, df)
