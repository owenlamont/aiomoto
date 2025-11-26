import json
from uuid import uuid4

import aioboto3
import pytest

from aiomoto import mock_aws


REGION = "us-east-1"


def _session() -> aioboto3.Session:
    return aioboto3.Session()


@pytest.mark.asyncio
async def test_create_queue_and_attributes_async() -> None:
    q_name = f"q-{uuid4().hex[:8]}"
    with mock_aws():
        async with _session().client("sqs", region_name=REGION) as sqs:
            queue_url = (await sqs.create_queue(QueueName=q_name, Attributes={}))[
                "QueueUrl"
            ]
            attributes = (
                await sqs.get_queue_attributes(
                    QueueUrl=queue_url, AttributeNames=["All"]
                )
            )["Attributes"]

    assert q_name in queue_url
    arn_parts = attributes["QueueArn"].split(":")
    assert arn_parts[-1] == q_name
    assert arn_parts[3] == REGION
    assert attributes["VisibilityTimeout"] == "30"


@pytest.mark.asyncio
async def test_send_receive_delete_message_async() -> None:
    q_name = f"q-{uuid4().hex[:8]}"
    with mock_aws():
        async with _session().resource("sqs", region_name=REGION) as sqs:
            queue = await sqs.create_queue(QueueName=q_name)
            send_resp = await queue.send_message(MessageBody="hello", DelaySeconds=0)

            messages = await queue.receive_messages(
                MaxNumberOfMessages=1, WaitTimeSeconds=0
            )
            assert len(messages) == 1
            message = messages[0]
            assert await message.body == "hello"
            assert send_resp["MessageId"] == await message.message_id

            await message.delete()
            remaining = await queue.receive_messages(
                MaxNumberOfMessages=1, WaitTimeSeconds=0
            )

    assert remaining == []


@pytest.mark.asyncio
async def test_create_queue_with_tags_and_policy_async() -> None:
    q_name = f"q-{uuid4().hex[:8]}"
    policy = {
        "Version": "2012-10-17",
        "Id": "test",
        "Statement": [{"Effect": "Allow", "Principal": "*", "Action": "*"}],
    }
    with mock_aws():
        async with _session().client("sqs", region_name=REGION) as sqs:
            queue_url = (
                await sqs.create_queue(
                    QueueName=q_name,
                    Attributes={"Policy": json.dumps(policy)},
                    tags={"tag_key_1": "tag_value_1", "tag_key_2": ""},
                )
            )["QueueUrl"]

            tags = (await sqs.list_queue_tags(QueueUrl=queue_url))["Tags"]
            attrs = (
                await sqs.get_queue_attributes(
                    QueueUrl=queue_url, AttributeNames=["Policy"]
                )
            )["Attributes"]

    assert tags == {"tag_key_1": "tag_value_1", "tag_key_2": ""}
    assert json.loads(attrs["Policy"]) == policy
