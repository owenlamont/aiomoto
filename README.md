# aiomoto

`aiomoto` is Moto for aiobotocore / aioboto3 (while staying compatible with classic
botocore / boto3). It adapts Moto's stubber so async and sync clients share the same
in-memory backend: you can write to a mock S3 bucket with boto3 and read it back via
aiobotocore or aioboto3 in the same process.

## Supported today

- `mock_aws()` usable as `with` or `async with`, guarding against real HTTP requests.
- Actively exercised in tests: S3 (CRUD + listings + streaming reads), DynamoDB
  (create/describe/put/get), Secrets Manager, SES, SNS, SQS, KMS, STS, Lambda, Events,
  Kafka/MSK, and s3fs async integration — all sharing one Moto backend between sync
  boto3/botocore and async aiobotocore/aioboto3 clients.
- Other Moto services often work out of the box through the same patch layer; if you
  hit a service-specific gap, open an issue with a minimal repro so we can add a
  focused slice.

For the evolving project roadmap, see the wiki: <https://github.com/owenlamont/aiomoto/wiki/Roadmap>

## Motivation

Like many others I've wanted to use Moto with aiobotocore and aioboto3 but found that
wasn't supported, see:

- <https://github.com/getmoto/moto/issues/2039>
- <https://github.com/getmoto/moto/issues/8694>

The primary motivation for attempting to create an aiomoto repo came from this issue
<https://github.com/getmoto/moto/issues/8513>
which states aiobotocore support is out of scope for moto and the current primary moto
maintainer suggested creating an aiomoto repo.

## Related Work

<https://github.com/dazza-codes/pytest-aiomoto> was an earlier attempt at this but not
really maintained now.

There is discussion on aiobotocore repo about moto support here
<https://github.com/aio-libs/aiobotocore/discussions/1300>

Both the above approaches as far as I'm aware rely on the Moto's
[server mode](https://docs.getmoto.org/en/latest/docs/server_mode.html) which I don't
want to use (mainly as I found server mode was slower than other local AWS services
like dynamodb-local in-memory and I also wanted to run tests in parallel without
worrying about port clashes or race conditions). In short I don't want any server and I
want aiomoto to support the moto like mock contexts in the same thread / process as the
tests run in.

## Installation

```bash
pip install aiomoto
```

aiomoto exposes the same Moto service extras, so you can install Moto plus the
dependencies required for the specific AWS services you use (for example
`aiomoto[s3]`, `aiomoto[dynamodb]`, or `aiomoto[all]`). Moto's extras are
service selectors for dependency sets (use `moto[all]` if you want everything),
rather than features provided by aiomoto itself. See the Moto install guide:
[Moto install guide](https://docs.getmoto.org/en/latest/docs/getting_started.html)

aiomoto-specific extras like `pandas` and `polars` behave like standard optional
dependencies, adding those libraries and their support stack on top of Moto.

Server mode requires Moto's server extra:

```bash
pip install "aiomoto[server]"
```

Pandas and Polars integrations are optional extras that add their own
dependencies:

```bash
pip install "aiomoto[pandas]"
pip install "aiomoto[polars]"
```

## Usage

Use `aiomoto.mock_aws` as a drop-in replacement for Moto's `mock_aws` that works
with both synchronous boto3/botocore clients and asynchronous aiobotocore/aioboto3
clients in the same process. It supports `with` and `async with` (and can decorate
sync/async callables).

### Use as a decorator

Use `@mock_aws` as a decorator when you want Moto started/stopped for the span of
a test function. Both sync and async callables are supported; omit parentheses
when you are not passing arguments (they remain optional to match Moto’s examples).
`mock_aws_decorator`
is also exported for teams that prefer an explicitly decorator-only name (or want
to preconfigure `reset` / `remove_data` once and reuse it) while leaving `mock_aws`
for context-manager usage.

```python
import boto3
from aiobotocore.session import AioSession
from aiomoto import mock_aws, mock_aws_decorator


@mock_aws
def test_sync_bucket() -> None:
    client = boto3.client("s3", region_name="us-east-1")
    client.create_bucket(Bucket="decorator-demo")


@mock_aws_decorator
async def test_async_bucket() -> None:
    async with AioSession().create_client("s3", region_name="us-east-1") as client:
        await client.create_bucket(Bucket="decorator-demo")
```

### Use as a context manager

```python
import boto3
from aiobotocore.session import AioSession
from aiomoto import mock_aws

async def demo():
    async with mock_aws():
        s3_sync = boto3.client("s3", region_name="us-east-1")
        s3_sync.create_bucket(Bucket="example")

        session = AioSession()
        async with session.create_client("s3", region_name="us-east-1") as s3_async:
            result = await s3_async.list_buckets()
            assert any(b["Name"] == "example" for b in result["Buckets"])
```

While aiomoto is active in in-process mode it prevents aiobotocore from issuing real
HTTP calls; any attempts fall back to Moto and will raise if they escape the
stubber. Avoid mixing raw Moto decorators with aiomoto contexts in the same test to
keep state aligned.

> aiomoto defaults to Moto’s **in-process** mode. Use
> `mock_aws(server_mode=True)` to run a local Moto server without in-process
> patches. In server mode, set `auto_endpoint` to control endpoint injection:
> `force` (default), `if_missing`, or `disabled`. Moto proxy mode remains
> unsupported. Server mode needs `moto[server]` installed.
>
> Server mode is typically slower than in-process mode, but it enables
> compatibility with Pandas and Polars S3 I/O (and other tooling that expects a
> real endpoint).

Server mode can also attach to an existing server by passing a `server_port`.
This keeps the context in “client mode” (no server start/stop) while still
injecting the endpoint. When aiomoto starts a server it records a registry file
under `AIOMOTO_SERVER_REGISTRY_DIR` and exposes the path via
`ctx.server_registry_path`.

Registry files use the pattern
`${AIOMOTO_SERVER_REGISTRY_DIR}/aiomoto-server-<uuid>.json`
and contain payloads like:

```json
{
  "endpoint": "http://127.0.0.1:12345",
  "host": "127.0.0.1",
  "pid": 1234,
  "port": 12345
}
```

### Server mode example

```python
import boto3
from aiomoto import AutoEndpointMode, mock_aws


def test_server_mode_force() -> None:
    with mock_aws(server_mode=True) as ctx:
        client = boto3.client("s3")
        assert client.meta.endpoint_url == ctx.server_endpoint
        client.create_bucket(Bucket="server-mode")


def test_server_mode_if_missing() -> None:
    with mock_aws(server_mode=True, auto_endpoint=AutoEndpointMode.IF_MISSING):
        client = boto3.client("s3", endpoint_url="http://example.com")
        assert client.meta.endpoint_url == "http://example.com"


def test_server_mode_disabled() -> None:
    with mock_aws(server_mode=True, auto_endpoint=AutoEndpointMode.DISABLED) as ctx:
        client = boto3.client("s3", endpoint_url=ctx.server_endpoint)
        client.create_bucket(Bucket="server-mode-explicit")


def test_server_mode_attach() -> None:
    with mock_aws(server_mode=True) as server:
        port = server.server_port
        assert port is not None
        # In another process, pass server_port to reuse the existing server.
        with mock_aws(server_mode=True, server_port=port) as client:
            assert client.server_endpoint == server.server_endpoint
```

### Pandas S3 in server mode

```python
import boto3
import pandas as pd
from aiomoto import mock_aws


def test_pandas_server_mode_csv() -> None:
    df = pd.DataFrame({"a": [1, 2], "b": ["x", "y"]})
    path = "s3://pandas-bucket/data.csv"

    with mock_aws(server_mode=True):
        boto3.client("s3").create_bucket(Bucket="pandas-bucket")
        # aiomoto patches pandas + fsspec/s3fs so s3:// routes to Moto.
        df.to_csv(path, index=False)
        result = pd.read_csv(path)

    assert result.equals(df)
```

Requires pandas + fsspec + s3fs for S3 access (pyarrow for parquet). You can
install the pinned pandas extra via `aiomoto[pandas]`.

### s3fs example

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

### DynamoDB example

```python
import boto3
from aiobotocore.session import AioSession
from aiomoto import mock_aws

AWS_REGION = "us-west-2"

async def demo():
    with mock_aws():
        # Sync write
        ddb_sync = boto3.client("dynamodb", region_name=AWS_REGION)
        ddb_sync.create_table(
            TableName="items",
            KeySchema=[{"AttributeName": "pk", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "pk", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        ddb_sync.put_item(TableName="items", Item={"pk": {"S": "from-sync"}})

        # Async read (aiobotocore)
        async with AioSession().create_client(
            "dynamodb", region_name=AWS_REGION
        ) as ddb_async:
            item = await ddb_async.get_item(
                TableName="items", Key={"pk": {"S": "from-sync"}}
            )
            assert item["Item"]["pk"]["S"] == "from-sync"
```

## Roadmap

The living roadmap sits in the wiki [Roadmap](https://github.com/owenlamont/aiomoto/wiki/Roadmap)

## Limitations

- Mixing raw Moto decorators with `aiomoto.mock_aws` in the same test is unsupported;
  the contexts manage shared state differently and can diverge.
- aiomoto wraps moto and patches aiobotocore; aioboto3 and s3fs should be covered
  automatically as they use aiobotocore clients/resources.
- We keep version ranges narrow and tested together, if you notice a new version of
  aiobotocore or moto that doesn't get covered feel free to raise an issue for this.
- s3fs caches filesystem instances; create them inside `mock_aws` and close them so
  finalizers don’t hit a closed or different event loop.
- Pandas S3 I/O: in server mode, aiomoto patches pandas to route `s3://` through
  fsspec/s3fs when those dependencies are installed.
- Polars S3 I/O is patched in server mode when polars is installed; aiomoto
  injects `storage_options` for `s3://` paths following the `auto_endpoint` mode.
