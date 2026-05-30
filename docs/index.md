---
icon: lucide/cloud
---

# aiomoto

## Moto-style AWS mocks for aiobotocore

`aiomoto` is [Moto](https://docs.getmoto.org/) for
[aiobotocore](https://github.com/aio-libs/aiobotocore), while staying compatible
with classic botocore / boto3. It adapts Moto's stubber so async and sync clients
share the same in-memory backend: you can write to a mock S3 bucket with boto3 and
read it back via aiobotocore in the same process.

<div class="grid cards" markdown>

-   :material-flash:{ .lg .middle } **One backend, both worlds**

    ---

    A single Moto backend is shared between synchronous boto3/botocore clients and
    asynchronous aiobotocore clients in the same process.

    [:octicons-arrow-right-24: Quick start](getting-started/quickstart.md)

-   :material-server-network:{ .lg .middle } **No server required**

    ---

    Defaults to Moto's in-process mode &mdash; fast, with no server to spin up or
    ports to manage. One flag opts into server mode for a real HTTP endpoint,
    such as pandas / polars S3 I/O.

    [:octicons-arrow-right-24: Server mode](guides/server-mode.md)

-   :material-table:{ .lg .middle } **Pandas & Polars S3**

    ---

    Optional integrations route `s3://` reads and writes through Moto in server
    mode for pandas and polars.

    [:octicons-arrow-right-24: DataFrame I/O](guides/dataframes.md)

-   :material-package-variant:{ .lg .middle } **Drop-in install**

    ---

    `pip install aiomoto`, then use `mock_aws` exactly like Moto &mdash; as a
    context manager or a decorator.

    [:octicons-arrow-right-24: Install](getting-started/installation.md)

</div>

## Quick start

```python
import boto3
from aiobotocore.session import AioSession
from aiomoto import mock_aws


async def demo() -> None:
    async with mock_aws():
        # Write with a synchronous boto3 client.
        boto3.client("s3", region_name="us-east-1").create_bucket(Bucket="example")

        # Read it back with an async aiobotocore client.
        session = AioSession()
        async with session.create_client("s3", region_name="us-east-1") as s3:
            result = await s3.list_buckets()
            assert any(b["Name"] == "example" for b in result["Buckets"])
```

## Supported today

- `mock_aws()` usable as `with` or `async with`, guarding against real HTTP requests.
- Actively exercised in tests: S3 (CRUD + listings + streaming reads), DynamoDB
  (create/describe/put/get), Secrets Manager, SES, SNS, SQS, KMS, STS, Lambda, Events,
  Kafka/MSK, and s3fs async integration &mdash; all sharing one Moto backend between
  sync boto3/botocore and async aiobotocore clients.
- Other Moto services often work out of the box through the same patch layer; if you
  hit a service-specific gap, open an issue with a minimal repro so we can add a
  focused slice.

## Next steps

<div class="grid cards" markdown>

-   [:octicons-download-24: __Install aiomoto__](getting-started/installation.md)

    pip, plus the Moto service extras and the pandas / polars integrations.

-   [:octicons-play-24: __Run your first mock__](getting-started/quickstart.md)

    Mock S3 from sync and async clients in under a minute.

-   [:octicons-book-24: __Guides__](guides/contexts-and-decorators.md)

    Contexts and decorators, server mode, and DataFrame I/O.

-   [:octicons-gear-24: __API reference__](reference/api.md)

    `mock_aws`, `mock_aws_decorator`, `AutoEndpointMode`, and the exception types.

</div>
