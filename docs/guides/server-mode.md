# Server mode

aiomoto defaults to Moto's **in-process** mode, which patches botocore and
aiobotocore so no server runs. Pass `server_mode=True` to start a local Moto server
instead:

```python
import boto3
from aiomoto import mock_aws


def test_server_mode() -> None:
    with mock_aws(server_mode=True) as ctx:
        client = boto3.client("s3")
        assert client.meta.endpoint_url == ctx.server_endpoint
        client.create_bucket(Bucket="server-mode")
```

!!! note "Requirements and trade-offs"

    Server mode needs `moto[server]` installed (`pip install "aiomoto[server]"`).
    It is typically slower than in-process mode, but it enables compatibility with
    pandas and polars S3 I/O and other tooling that expects a real endpoint. Moto's
    proxy mode remains unsupported.

## Endpoint injection

In server mode, `auto_endpoint` controls whether aiomoto rewrites client endpoints
to point at the local server. Pass an [`AutoEndpointMode`](../reference/api.md#autoendpointmode):

| Mode         | Value         | Behaviour                                                       |
| ------------ | ------------- | -------------------------------------------------------------- |
| `FORCE`      | `"force"`     | Always inject the server endpoint (the default in server mode).|
| `IF_MISSING` | `"if_missing"`| Inject only when the client has no explicit `endpoint_url`.    |
| `DISABLED`   | `"disabled"`  | Never inject; clients must target the server themselves.       |

```python
import boto3
from aiomoto import AutoEndpointMode, mock_aws


def test_force() -> None:
    with mock_aws(server_mode=True) as ctx:
        client = boto3.client("s3")
        assert client.meta.endpoint_url == ctx.server_endpoint
        client.create_bucket(Bucket="server-mode")


def test_if_missing() -> None:
    with mock_aws(server_mode=True, auto_endpoint=AutoEndpointMode.IF_MISSING):
        client = boto3.client("s3", endpoint_url="http://example.com")
        assert client.meta.endpoint_url == "http://example.com"


def test_disabled() -> None:
    with mock_aws(server_mode=True, auto_endpoint=AutoEndpointMode.DISABLED) as ctx:
        client = boto3.client("s3", endpoint_url=ctx.server_endpoint)
        client.create_bucket(Bucket="server-mode-explicit")
```

`auto_endpoint` requires `server_mode=True`; supplying any mode other than
`DISABLED` in in-process mode raises
[`AutoEndpointError`](../reference/api.md#exceptions).

## Attaching to an existing server

Pass a `server_port` to attach to a server that is already running rather than
starting a new one. This keeps the context in "client mode" (no server start/stop)
while still injecting the endpoint:

```python
from aiomoto import mock_aws


def test_attach() -> None:
    with mock_aws(server_mode=True) as server:
        port = server.server_port
        assert port is not None
        # In another process, pass server_port to reuse the existing server.
        with mock_aws(server_mode=True, server_port=port) as client:
            assert client.server_endpoint == server.server_endpoint
```

## Parallel test runs

Server mode is safe under parallel test runners such as
[pytest-xdist](https://pytest-xdist.readthedocs.io/). Each xdist worker is a separate
process, so a `mock_aws(server_mode=True)` context in one worker starts its own Moto
server on an OS-assigned ephemeral port with a fully isolated backend &mdash; there
are no port clashes and no shared state between workers.

### Recommended fixture layout

A Moto server is comparatively slow to start, so the recommended pattern is to start
**one server per worker** and keep it alive for the whole session, then create and
tear down resources (S3 buckets, DynamoDB tables, and so on) per test:

- A **session-scoped, `autouse`** fixture enters `mock_aws(server_mode=True)` once.
  xdist runs each worker in its own process, so every worker gets its own server.
- **Function-scoped** fixtures create the resources a test needs and remove them when
  the test finishes, so Moto's persistent backends don't leak state between tests.

```python title="conftest.py"
from collections.abc import Iterator

import boto3
from mypy_boto3_s3.service_resource import Bucket
import pytest

from aiomoto import mock_aws


@pytest.fixture(scope="session", autouse=True)
def aiomoto_context() -> Iterator[None]:
    """Start one Moto server per xdist worker, kept alive for the whole session."""
    with mock_aws(server_mode=True):
        yield


@pytest.fixture
def s3_bucket() -> Iterator[Bucket]:
    """Create an S3 bucket for a single test, then tear it down afterwards."""
    s3 = boto3.resource("s3", region_name="us-east-1")
    bucket = s3.Bucket("example-bucket")
    bucket.create()
    yield bucket
    bucket.objects.all().delete()
    bucket.delete()
```

```python title="test_s3.py"
from mypy_boto3_s3.service_resource import Bucket


def test_round_trip(s3_bucket: Bucket) -> None:
    s3_bucket.put_object(Key="hello.txt", Body=b"hi")
    assert s3_bucket.Object("hello.txt").get()["Body"].read() == b"hi"
```

The fixture yields a strongly typed boto3
[`Bucket`](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/service-resource/index.html)
resource bound to the test's bucket, so tests work with the bucket object directly
instead of passing its name around. The `Bucket` type comes from
[boto3-stubs](https://pypi.org/project/boto3-stubs/) (`pip install "boto3-stubs[s3]"`),
a type-checking-only dependency; import it under `typing.TYPE_CHECKING` if you would
rather not import it at runtime.

Run it with xdist as usual:

```bash
pytest -n logical
```

Each worker starts its server once, every test gets a clean `example-bucket`, and a
bucket in one worker never collides with another worker's because each worker has its
own isolated backend.

## Server registry files

When aiomoto starts a server it records a registry file under the directory named by
the `AIOMOTO_SERVER_REGISTRY_DIR` environment variable and exposes the path via
`ctx.server_registry_path`. Files use the pattern:

```text
${AIOMOTO_SERVER_REGISTRY_DIR}/aiomoto-server-<uuid>.json
```

and contain payloads like:

```json
{
  "endpoint": "http://127.0.0.1:12345",
  "host": "127.0.0.1",
  "pid": 1234,
  "port": 12345
}
```

Registry entries older than 24 hours are treated as stale and cleaned up when a new
server is started.

## Context attributes

In server mode the context exposes these read-only attributes:

| Attribute               | Description                                          |
| ----------------------- | ---------------------------------------------------- |
| `server_endpoint`       | The base URL of the running server.                  |
| `server_host`           | The host the server bound to.                        |
| `server_port`           | The port the server bound to.                        |
| `server_registry_path`  | Path to the registry file aiomoto wrote.             |
