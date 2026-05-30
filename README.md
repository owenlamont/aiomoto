# aiomoto

`aiomoto` is Moto for aiobotocore (while staying compatible with classic
botocore / boto3). It adapts Moto's stubber so async and sync clients share the same
in-memory backend: you can write to a mock S3 bucket with boto3 and read it back via
aiobotocore in the same process.

📖 **Full documentation: <https://aiomoto-docs.pages.dev/>**

## Supported today

- `mock_aws()` usable as `with` or `async with`, guarding against real HTTP requests.
- Actively exercised in tests: S3 (CRUD + listings + streaming reads), DynamoDB
  (create/describe/put/get), Secrets Manager, SES, SNS, SQS, KMS, STS, Lambda, Events,
  Kafka/MSK, and s3fs async integration — all sharing one Moto backend between sync
  boto3/botocore and async aiobotocore clients.
- Other Moto services often work out of the box through the same patch layer; if you
  hit a service-specific gap, open an issue with a minimal repro so we can add a
  focused slice.

## Installation

```bash
pip install aiomoto
```

aiomoto re-exposes Moto's service extras (for example `aiomoto[s3]`,
`aiomoto[dynamodb]`, or `aiomoto[all]`), plus aiomoto-specific extras
(`aiomoto[server]`, `aiomoto[pandas]`, `aiomoto[polars]`). See the
[installation guide](https://aiomoto-docs.pages.dev/getting-started/installation/)
for details.

## Usage

Use `aiomoto.mock_aws` as a drop-in replacement for Moto's `mock_aws` that works
with both synchronous boto3/botocore clients and asynchronous aiobotocore clients in
the same process. It supports `with`, `async with`, and decorating sync/async
callables.

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

The documentation covers more:

- [Contexts and decorators](https://aiomoto-docs.pages.dev/guides/contexts-and-decorators/)
  — `with` / `async with`, `@mock_aws`, `reset` / `remove_data`, and the
  `AWS_ENDPOINT_URL` gotcha.
- [Server mode](https://aiomoto-docs.pages.dev/guides/server-mode/) — run a local
  Moto server, endpoint-injection modes, and attaching to an existing server.
- [Pandas and Polars](https://aiomoto-docs.pages.dev/guides/dataframes/) — `s3://`
  DataFrame I/O.
- [Examples](https://aiomoto-docs.pages.dev/examples/) — S3, DynamoDB, SQS, SNS,
  s3fs, and streaming reads.
- [API reference](https://aiomoto-docs.pages.dev/reference/api/) — `mock_aws`,
  `mock_aws_decorator`, `AutoEndpointMode`, and the exception types.

## Motivation

Like many others I've wanted to use Moto with aiobotocore but found that wasn't
supported. The
[motivation page](https://aiomoto-docs.pages.dev/about/motivation/) explains the
background and why aiomoto avoids depending on Moto's server mode by default.

## Limitations

aiomoto keeps version ranges narrow and tested together, and a few integrations
(notably pandas/polars S3 I/O) only work in server mode. See the
[limitations page](https://aiomoto-docs.pages.dev/about/limitations/) for the full
list, including free-threaded CPython support.
