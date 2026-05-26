from __future__ import annotations

import json
from uuid import uuid4

from aiobotocore.session import AioSession
import pytest

from aiomoto import mock_aws


REGION = "us-east-1"


@pytest.mark.asyncio
async def test_create_queue_and_attributes_async() -> None:
    q_name = f"q-{uuid4().hex[:8]}"
    with mock_aws():
        async with AioSession().create_client("sqs", region_name=REGION) as sqs:
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
        async with AioSession().create_client("sqs", region_name=REGION) as sqs:
            queue_url = (await sqs.create_queue(QueueName=q_name))["QueueUrl"]
            send_resp = await sqs.send_message(
                QueueUrl=queue_url, MessageBody="hello", DelaySeconds=0
            )

            received = await sqs.receive_message(
                QueueUrl=queue_url, MaxNumberOfMessages=1, WaitTimeSeconds=0
            )
            messages = received.get("Messages", [])
            assert len(messages) == 1
            message = messages[0]
            assert message["Body"] == "hello"
            assert send_resp["MessageId"] == message["MessageId"]

            await sqs.delete_message(
                QueueUrl=queue_url, ReceiptHandle=message["ReceiptHandle"]
            )
            remaining = await sqs.receive_message(
                QueueUrl=queue_url, MaxNumberOfMessages=1, WaitTimeSeconds=0
            )

    assert remaining.get("Messages", []) == []


@pytest.mark.asyncio
async def test_create_queue_with_tags_and_policy_async() -> None:
    q_name = f"q-{uuid4().hex[:8]}"
    policy = {
        "Version": "2012-10-17",
        "Id": "test",
        "Statement": [{"Effect": "Allow", "Principal": "*", "Action": "*"}],
    }
    with mock_aws():
        async with AioSession().create_client("sqs", region_name=REGION) as sqs:
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
