from __future__ import annotations

import pandas as pd
import pandas.testing as pdt
import s3fs  # type: ignore[import-untyped]

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
