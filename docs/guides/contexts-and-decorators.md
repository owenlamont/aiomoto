# Contexts and decorators

`mock_aws` is a single callable that adapts to how you use it: as a context manager
(`with` / `async with`) or as a decorator over a sync or async function.

## Context manager

```python
import boto3
from aiomoto import mock_aws


def test_with_block() -> None:
    with mock_aws():
        boto3.client("s3", region_name="us-east-1").create_bucket(Bucket="demo")
```

The same object supports `async with`, which is required when the body needs an
event loop (for example when using aiobotocore clients):

```python
from aiobotocore.session import AioSession
from aiomoto import mock_aws


async def demo() -> None:
    async with mock_aws():
        async with AioSession().create_client("s3", region_name="us-east-1") as s3:
            await s3.create_bucket(Bucket="demo")
```

## Decorator

`@mock_aws` starts Moto before the wrapped function runs and stops it afterwards.
Omit the parentheses when you are not passing arguments (they remain optional to
match Moto's examples):

```python
from aiomoto import mock_aws


@mock_aws
def test_sync() -> None: ...


@mock_aws(reset=False)
def test_sync_no_reset() -> None: ...
```

### `mock_aws_decorator`

`mock_aws_decorator` is exported for teams that prefer an explicitly decorator-only
name, or that want to preconfigure options once and reuse them:

```python
from aiomoto import mock_aws_decorator


# Preconfigure once, reuse as a decorator.
mock_no_reset = mock_aws_decorator(reset=False, remove_data=False)


@mock_no_reset
async def test_async() -> None: ...
```

Calling `mock_aws_decorator(...)` with keyword arguments returns a reusable
context/decorator instance; calling it directly on a function (`@mock_aws_decorator`)
wraps that function with the defaults.

## Reset and data removal

Both `mock_aws` and `mock_aws_decorator` accept `reset` and `remove_data` (each
defaulting to `True`):

| Parameter     | Default | Effect                                                        |
| ------------- | ------- | ------------------------------------------------------------- |
| `reset`       | `True`  | Reset Moto's backends when the context starts.                |
| `remove_data` | `True`  | Remove backend data when the context exits.                   |

Leaving both at their defaults gives each test an isolated, empty AWS environment.

## Nesting

Nesting `mock_aws` is safe, and nested contexts **share a single Moto backend**
rather than getting isolated state. While an outer context is active, entering an
inner one &mdash; whether the same context object re-entered or a separate
`mock_aws()` block &mdash; does not reset the backend, and exiting it does not remove
data. The backend is reset only on the outermost enter and torn down only on the
outermost exit.

In practice this means you can combine a decorator with an inner `with mock_aws():`
block without losing state: the inner block sees everything the outer set up, and
anything it creates stays visible after it exits.

```python
import boto3
from aiomoto import mock_aws


@mock_aws
def test_nested() -> None:
    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket="outer")

    with mock_aws():
        # The inner context shares the outer's backend (no reset).
        assert any(b["Name"] == "outer" for b in s3.list_buckets()["Buckets"])
        s3.create_bucket(Bucket="inner")

    # The inner bucket is still here after the inner block exits.
    names = {b["Name"] for b in s3.list_buckets()["Buckets"]}
    assert names == {"outer", "inner"}
```

!!! note "Inner `reset` / `remove_data` are ignored while nested"

    Because the Moto backend is shared and ref-counted, an inner context's `reset`
    and `remove_data` flags have no effect while an outer context is active &mdash;
    only the outermost context's settings apply.

## The `AWS_ENDPOINT_URL` gotcha

In-process mode inherits Moto's URL-matching behaviour. Ambient endpoint
configuration such as `AWS_ENDPOINT_URL=http://localhost:4566` can make boto3 or
aiobotocore target that endpoint instead of a normal AWS service URL, which means
Moto will not intercept the request.

If your environment sets `AWS_ENDPOINT_URL`:

- Unset it for in-process tests, **or**
- Set `AWS_IGNORE_CONFIGURED_ENDPOINT_URLS=true` so botocore ignores configured
  endpoint URLs.

If you intentionally need clients to use a local HTTP endpoint, prefer
[server mode](server-mode.md) instead.
