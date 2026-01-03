from __future__ import annotations

import sys

import pytest


# Free-threaded CPython (PYTHON_GIL=0 / 3.14t) forces pandas to enable the GIL at
# import time, emitting a RuntimeWarning that is treated as an error in our
# warnings-as-errors config. Skip the module on such interpreters.
if hasattr(sys, "_is_gil_enabled") and not sys._is_gil_enabled():  # pragma: no cover
    pytest.skip(
        "pandas is not yet compatible with free-threaded CPython builds",
        allow_module_level=True,
    )

import pandas as pd
import pandas.testing as pdt
import s3fs

from aiomoto import mock_aws


def test_pandas_parquet_via_fsspec_storage_options() -> None:
    df = pd.DataFrame({"a": [1, 2], "b": ["x", "y"]})
    path = "s3://bucket-pandas/data.parquet"

    with mock_aws():
        fs = s3fs.S3FileSystem(anon=False, asynchronous=False)
        fs.call_s3("create_bucket", Bucket="bucket-pandas")

        df.to_parquet(path, filesystem=fs)
        result = pd.read_parquet(path, filesystem=fs)

    pdt.assert_frame_equal(result, df)
