# Examples

These examples all use in-process mode (the default). Each one shows the aiomoto
signature: a single Moto backend shared between synchronous boto3 clients and
asynchronous aiobotocore clients.

## S3: write sync, read async

```python
import boto3
from aiobotocore.session import AioSession
from aiomoto import mock_aws


async def demo() -> None:
    async with mock_aws():
        s3_sync = boto3.client("s3", region_name="us-east-1")
        s3_sync.create_bucket(Bucket="example")
        s3_sync.put_object(Bucket="example", Key="hello.txt", Body=b"hi")

        session = AioSession()
        async with session.create_client("s3", region_name="us-east-1") as s3_async:
            response = await s3_async.get_object(Bucket="example", Key="hello.txt")
            async with response["Body"] as stream:
                assert await stream.read() == b"hi"
```

The streaming `Body` is an async context manager that mirrors aiohttp's
`ClientResponse`, so `async with` and `await stream.read()` work as expected.

## DynamoDB

```python
import boto3
from aiobotocore.session import AioSession
from aiomoto import mock_aws

AWS_REGION = "us-west-2"


async def demo() -> None:
    with mock_aws():
        # Sync write.
        ddb_sync = boto3.client("dynamodb", region_name=AWS_REGION)
        ddb_sync.create_table(
            TableName="items",
            KeySchema=[{"AttributeName": "pk", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "pk", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        ddb_sync.put_item(TableName="items", Item={"pk": {"S": "from-sync"}})

        # Async read (aiobotocore).
        async with AioSession().create_client(
            "dynamodb", region_name=AWS_REGION
        ) as ddb_async:
            item = await ddb_async.get_item(
                TableName="items", Key={"pk": {"S": "from-sync"}}
            )
            assert item["Item"]["pk"]["S"] == "from-sync"
```

## SQS

```python
from aiobotocore.session import AioSession
from aiomoto import mock_aws


async def demo() -> None:
    async with mock_aws():
        async with AioSession().create_client("sqs", region_name="us-east-1") as sqs:
            queue = await sqs.create_queue(QueueName="jobs")
            url = queue["QueueUrl"]
            await sqs.send_message(QueueUrl=url, MessageBody="ping")
            received = await sqs.receive_message(QueueUrl=url)
            assert received["Messages"][0]["Body"] == "ping"
```

## SNS

```python
from aiobotocore.session import AioSession
from aiomoto import mock_aws


async def demo() -> None:
    async with mock_aws():
        async with AioSession().create_client("sns", region_name="us-east-1") as sns:
            topic = await sns.create_topic(Name="alerts")
            await sns.publish(TopicArn=topic["TopicArn"], Message="hello")
```

## Secrets Manager

```python
import boto3
from aiomoto import mock_aws


def test_secrets() -> None:
    with mock_aws():
        client = boto3.client("secretsmanager", region_name="us-east-1")
        client.create_secret(Name="token", SecretString="s3cr3t")
        assert client.get_secret_value(SecretId="token")["SecretString"] == "s3cr3t"
```

## s3fs

s3fs runs on aiobotocore under the hood, so it works in in-process mode:

```python
import s3fs
from aiomoto import mock_aws


def test_s3fs() -> None:
    with mock_aws():
        fs = s3fs.S3FileSystem(asynchronous=False, anon=False)
        fs.call_s3("create_bucket", Bucket="bucket-123")
        fs.call_s3("put_object", Bucket="bucket-123", Key="test.txt", Body=b"hi")
        assert fs.cat("bucket-123/test.txt") == b"hi"
```

## More

- [Server mode](guides/server-mode.md) examples for force / if-missing / disabled
  endpoint injection and attaching to an existing server.
- [Pandas and Polars](guides/dataframes.md) for `s3://` DataFrame I/O.
