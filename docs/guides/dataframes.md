# Pandas and Polars

pandas and polars read and write `s3://` paths through fsspec/s3fs and their own
object-store layers, which expect a real HTTP endpoint. aiomoto wires these up in
[server mode](server-mode.md): it patches the DataFrame libraries so `s3://` routes
to the local Moto server.

!!! note "Server mode required"

    DataFrame S3 I/O is patched only in server mode, because the underlying
    libraries need a real endpoint. Install the relevant extra
    (`aiomoto[pandas]` or `aiomoto[polars]`) so the dependencies are present.

## Pandas

`aiomoto[pandas]` installs pandas, Moto's server extra, and the S3 stack (`fsspec`,
`s3fs`, and `pyarrow` for parquet). With server mode active, aiomoto patches
pandas + fsspec/s3fs so `s3://` paths reach Moto:

```python
import boto3
import pandas as pd
from aiomoto import mock_aws


def test_pandas_server_mode_csv() -> None:
    df = pd.DataFrame({"a": [1, 2], "b": ["x", "y"]})
    path = "s3://pandas-bucket/data.csv"

    with mock_aws(server_mode=True):
        boto3.client("s3").create_bucket(Bucket="pandas-bucket")
        df.to_csv(path, index=False)
        result = pd.read_csv(path)

    assert result.equals(df)
```

aiomoto only patches pandas when `fsspec` and `s3fs` are both importable; the
`aiomoto[pandas]` extra installs both (plus `pyarrow` for parquet), so the
integration is active out of the box.

## Polars

`aiomoto[polars]` installs polars and Moto's server extra. In server mode aiomoto
injects `storage_options` for `s3://` paths, following the `auto_endpoint` mode:

```python
import boto3
import polars as pl
from aiomoto import mock_aws


def test_polars_server_mode_parquet() -> None:
    df = pl.DataFrame({"a": [1, 2], "b": ["x", "y"]})
    path = "s3://polars-bucket/data.parquet"

    with mock_aws(server_mode=True):
        boto3.client("s3").create_bucket(Bucket="polars-bucket")
        df.write_parquet(path)
        result = pl.read_parquet(path)

    assert result.equals(df)
```

## s3fs

s3fs uses aiobotocore clients underneath, so it is covered automatically in
in-process mode &mdash; no server required:

```python
import s3fs
from aiomoto import mock_aws


def test_s3fs_sync_usage() -> None:
    with mock_aws():
        fs = s3fs.S3FileSystem(asynchronous=False, anon=False)
        fs.call_s3("create_bucket", Bucket="bucket-123")
        fs.call_s3("put_object", Bucket="bucket-123", Key="test.txt", Body=b"hi")
        assert fs.cat("bucket-123/test.txt") == b"hi"
```

!!! warning "Close filesystems inside the context"

    s3fs caches filesystem instances. Create them inside `mock_aws` and close them
    so finalizers don't run against a closed or different event loop.
