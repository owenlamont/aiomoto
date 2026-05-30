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

Contexts are re-entrant: entering an already-active context simply increases an
internal depth counter, and the backend is only torn down when the outermost
context exits. This makes it safe to combine a decorator with an inner `with
mock_aws():` block without losing state.

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
