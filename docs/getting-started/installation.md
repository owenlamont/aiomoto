# Installation

aiomoto is published on PyPI:

```bash
pip install aiomoto
```

It requires Python 3.11 or newer and pulls in `aiobotocore`, `moto`, and
`platformdirs`.

## Service extras

aiomoto re-exposes Moto's service extras, so you can install Moto plus the
dependencies required for the specific AWS services you use:

=== "S3"

    ```bash
    pip install "aiomoto[s3]"
    ```

=== "DynamoDB"

    ```bash
    pip install "aiomoto[dynamodb]"
    ```

=== "Everything"

    ```bash
    pip install "aiomoto[all]"
    ```

Moto's extras are service selectors for dependency sets (use `all` if you want
everything) rather than features provided by aiomoto itself. See the
[Moto install guide](https://docs.getmoto.org/en/latest/docs/getting_started.html)
for the full list.

## Server mode

[Server mode](../guides/server-mode.md) runs a local Moto server instead of
patching in process. It needs Moto's `server` extra:

```bash
pip install "aiomoto[server]"
```

## Pandas and Polars

These integrations bundle everything needed for `s3://` DataFrame I/O, which always
runs through [server mode](../guides/server-mode.md):

=== "Pandas"

    ```bash
    pip install "aiomoto[pandas]"
    ```

    Pulls in pandas, Moto's server extra, and the S3 stack (`fsspec`, `s3fs`, and
    `pyarrow` for parquet).

=== "Polars"

    ```bash
    pip install "aiomoto[polars]"
    ```

    Pulls in polars and Moto's server extra; polars reads `s3://` through its
    native object-store layer.

See [Pandas and Polars](../guides/dataframes.md) for how `s3://` paths are routed
through Moto.

## Verify the install

```python
import aiomoto

print(aiomoto.__version__)
```

Continue to the [Quick start](quickstart.md) to mock your first AWS service.
