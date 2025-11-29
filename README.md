# aiomoto

`aiomoto` is Moto for aiobotocore / aioboto3 (while staying compatible with classic
botocore / boto3). It adapts Moto's stubber so async and sync clients share the same
in-memory backend: you can write to a mock S3 bucket with boto3 and read it back via
aiobotocore or aioboto3 in the same process.

## Supported today

- `mock_aws()` usable as `with` or `async with`, guarding against real HTTP requests.
- S3 bucket + object CRUD across sync/async clients and resources, including empty
  bodies, overwrites, metadata, and streaming reads.
- S3 listings (client + resource) keep key names intact, including odd byte sequences,
  prefixes with `Delimiter` and `EncodingType=url`, while preserving headers needed by
  aiobotocore parsers.
- DynamoDB table create/describe and put/get flows through aiobotocore/aioboto3
  clients/resources while boto3 sees the same regional backends, including
  missing-table errors and cross-visibility between sync and async calls.
- Secrets Manager create/list/get/delete via aiobotocore/aioboto3 while sharing Moto
  state with boto3, covering staging labels and forced deletions.
- SES verify identity/address and send_email/send_raw_email through async clients with
  message IDs preserved and real HTTP guarded; boto3 and async clients share send quotas
  and verified identities.
- Other AWS services may work out of the box through the same patch layer; if you hit
  a service-specific gap, please open an issue with a minimal repro so we can add a
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

## Usage

Use `aiomoto.mock_aws` as a drop-in replacement for Moto's `mock_aws` that works
with both synchronous boto3/botocore clients and asynchronous aiobotocore/aioboto3
clients in the same process. It supports `with` and `async with` (and can decorate
sync/async callables).

### Use as a decorator

Use `@mock_aws` as a decorator when you want Moto started/stopped for the span of
a test function. Both sync and async callables are supported (parentheses are
optional to match Moto’s examples). `mock_aws_decorator`
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


@mock_aws_decorator()
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

While aiomoto is active it prevents aiobotocore from issuing real HTTP calls; any
attempts fall back to Moto and will raise if they escape the stubber. Avoid mixing
raw Moto decorators with aiomoto contexts in the same test to keep state aligned.

> aiomoto supports Moto’s **in-process** mode only. Moto server/proxy modes
> (`TEST_SERVER_MODE`, proxy mode) will raise at `mock_aws()` time so you don’t
> accidentally depend on real network calls.

### s3fs (async) example

When using s3fs, prefer its async interface and supply an
`aiobotocore.session.AioSession` plus a running loop; close the client explicitly to
avoid event-loop shutdown races inside fsspec’s sync wrappers.

```python
import asyncio
import aiobotocore.session
import pytest
import s3fs

from aiomoto import mock_aws


@pytest.mark.asyncio
async def test_s3fs_async_usage() -> None:
    session = aiobotocore.session.AioSession()
    fs = s3fs.S3FileSystem(
        asynchronous=True,
        session=session,
        loop=asyncio.get_running_loop(),
    )
    with mock_aws():
        await fs._call_s3("create_bucket", Bucket="bucket-123")
        await fs._call_s3(
            "put_object", Bucket="bucket-123", Key="test.txt", Body=b"hi"
        )
        assert await fs._cat_file("bucket-123/test.txt") == b"hi"
    await fs._s3.close()
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

- Mixing raw Moto decorators with `aiomoto.mock_aws()` in the same test is unsupported;
  the contexts manage shared state differently and can diverge.
- aiomoto wraps moto and patches aiobotocore; aioboto3 and s3fs should be covered
  automatically as they use aiobotocore clients/resources.
- We keep version ranges narrow and tested together, if you notice a new version of
  aiobotocore or moto that doesn't get covered feel free to raise an issue for this.
