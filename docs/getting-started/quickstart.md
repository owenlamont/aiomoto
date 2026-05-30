# Quick start

`aiomoto.mock_aws` is a drop-in replacement for Moto's `mock_aws` that works with
both synchronous boto3/botocore clients and asynchronous aiobotocore clients in the
same process. It supports `with`, `async with`, and decorating sync or async
callables.

## As a context manager

The defining feature of aiomoto is that one Moto backend is shared across sync and
async clients. Write with boto3, read with aiobotocore:

```python
import boto3
from aiobotocore.session import AioSession
from aiomoto import mock_aws


async def demo() -> None:
    async with mock_aws():
        s3_sync = boto3.client("s3", region_name="us-east-1")
        s3_sync.create_bucket(Bucket="example")

        session = AioSession()
        async with session.create_client("s3", region_name="us-east-1") as s3_async:
            result = await s3_async.list_buckets()
            assert any(b["Name"] == "example" for b in result["Buckets"])
```

A plain `with mock_aws():` block works too when you only need synchronous clients.

## As a decorator

Use `@mock_aws` as a decorator to start and stop Moto for the span of a test
function. Both sync and async callables are supported; the parentheses are optional:

```python
import boto3
from aiobotocore.session import AioSession
from aiomoto import mock_aws


@mock_aws
def test_sync_bucket() -> None:
    client = boto3.client("s3", region_name="us-east-1")
    client.create_bucket(Bucket="decorator-demo")


@mock_aws
async def test_async_bucket() -> None:
    async with AioSession().create_client("s3", region_name="us-east-1") as client:
        await client.create_bucket(Bucket="decorator-demo")
```

!!! tip "Prefer an explicit decorator name?"

    `mock_aws_decorator` is also exported for teams that want an explicitly
    decorator-only name, or that want to preconfigure `reset` / `remove_data` once
    and reuse it, while leaving `mock_aws` for context-manager usage. See
    [Contexts and decorators](../guides/contexts-and-decorators.md).

## Blocking real requests

While aiomoto is active in in-process mode it prevents aiobotocore from issuing real
HTTP calls; any attempt that escapes the stubber raises
[`RealHTTPRequestBlockedError`](../reference/api.md#exceptions). This keeps tests
hermetic &mdash; a call to an unmocked endpoint fails loudly instead of reaching the
real internet.

!!! warning "Don't mix raw Moto decorators with aiomoto"

    Avoid mixing raw Moto decorators with aiomoto contexts in the same test. The
    two manage shared state differently and can diverge.

## Next steps

- [Contexts and decorators](../guides/contexts-and-decorators.md) &mdash; reset and
  data-removal options, nesting, and the `AWS_ENDPOINT_URL` gotcha.
- [Server mode](../guides/server-mode.md) &mdash; run a real local Moto server when
  you need an HTTP endpoint.
- [Examples](../examples.md) &mdash; S3, DynamoDB, SQS, SNS, s3fs, and streaming
  reads.
