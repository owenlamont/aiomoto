# aiomoto

`aiomoto` aims to be Moto for aiobotocore / aioboto3 (plus synchronous botocore / boto3
). Specifically it is supposed to adapter for moto to aiobotocore. I aim to be able to
mock both asynchronous and synchronous service clients with consistent state between
both, i.e. I want you to be able to synchronously write a file to a mock S3 bucket with
boto3 and asynchronously read the same file back again using aioboto3 or aiobotocore.
S3 object put/get (including empty bodies) and streaming reads now work across sync
and async clients/resources while sharing the same Moto backend state.

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

Use `aiomoto.mock_aws()` as a drop-in replacement for Moto's `mock_aws` that works
with both synchronous boto3/botocore clients and asynchronous aiobotocore/aioboto3
clients in the same process. It supports `with` and `async with` (and may also
decorate sync/async callables).

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

## Roadmap

This is early days and nothing in aiomoto is functional yet. I'd like to get services
I personally use heavily like DynamoDb, S3 and some other more niche services working
early. If that all goes well I'd welcome contributors to start adding support for other
AWS services I don't personally use. I hope to be able to re-use much of motos automated
tests for aiomoto too.

## Limitations

I don't plan to support mixing both moto and aiomoto contexts in the same tests,
that'd be really complicated to get to sync... however I want aiomoto to be like a super
set of moto for the services it does implement. So a aiomoto mock context will patch
both boto3 / botocore and aiobotocore / aioboto3. Not sure how complicated this patching
is going to be yet but we'll see.

Since aiomoto will be tightly coupled to both aiobotocore and moto for now I intend it
to pin both of those dependencies exactly.
