# Installation

aiomoto is published on PyPI and requires Python 3.11 or newer (it pulls in
`aiobotocore`, `moto`, and `platformdirs`).

=== "pip"

    ```bash
    pip install aiomoto
    ```

=== "uv"

    ```bash
    uv add aiomoto
    ```

## Service extras

aiomoto re-exposes Moto's service extras, so you can install Moto plus the
dependencies required for the specific AWS services you use &mdash; for example S3:

=== "pip"

    ```bash
    pip install "aiomoto[s3]"
    ```

=== "uv"

    ```bash
    uv add "aiomoto[s3]"
    ```

Swap `s3` for any service you need (`dynamodb`, `sqs`, …), or use `all` for
everything. Moto's extras are service selectors for dependency sets rather than
features provided by aiomoto itself. See the
[Moto install guide](https://docs.getmoto.org/en/latest/docs/getting_started.html)
for the full list.

## Server mode

[Server mode](../guides/server-mode.md) runs a local Moto server instead of
patching in process. It needs Moto's `server` extra:

=== "pip"

    ```bash
    pip install "aiomoto[server]"
    ```

=== "uv"

    ```bash
    uv add "aiomoto[server]"
    ```

## Pandas and Polars

These integrations bundle everything needed for `s3://` DataFrame I/O, which always
runs through [server mode](../guides/server-mode.md).

The `pandas` extra pulls in pandas, Moto's server extra, and the S3 stack (`fsspec`,
`s3fs`, and `pyarrow` for parquet):

=== "pip"

    ```bash
    pip install "aiomoto[pandas]"
    ```

=== "uv"

    ```bash
    uv add "aiomoto[pandas]"
    ```

The `polars` extra pulls in polars and Moto's server extra; polars reads `s3://`
through its native object-store layer:

=== "pip"

    ```bash
    pip install "aiomoto[polars]"
    ```

=== "uv"

    ```bash
    uv add "aiomoto[polars]"
    ```

See [Pandas and Polars](../guides/dataframes.md) for how `s3://` paths are routed
through Moto.

## Verify the install

```python
import aiomoto

print(aiomoto.__version__)
```

Continue to the [Quick start](quickstart.md) to mock your first AWS service.
