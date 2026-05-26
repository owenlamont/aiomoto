from __future__ import annotations

from uuid import uuid4

from aiobotocore.session import AioSession
import pytest

from aiomoto import mock_aws


REGION = "us-east-1"
ACCOUNT_ID = "123456789012"


@pytest.mark.asyncio
async def test_create_and_delete_topic_async() -> None:
    topic_name = f"topic-{uuid4().hex[:6]}"
    with mock_aws():
        async with AioSession().create_client("sns", region_name=REGION) as sns:
            await sns.create_topic(Name=topic_name)
            topics = (await sns.list_topics())["Topics"]
            assert len(topics) == 1
            topic_arn = topics[0]["TopicArn"]
            expected_arn = f"arn:aws:sns:{REGION}:{ACCOUNT_ID}:{topic_name}"
            assert topic_arn == expected_arn

            await sns.delete_topic(TopicArn=topic_arn)
            await sns.delete_topic(TopicArn=topic_arn)  # idempotent

            assert (await sns.list_topics())["Topics"] == []


@pytest.mark.asyncio
async def test_topic_attributes_and_tags_async() -> None:
    topic_name = f"topic-{uuid4().hex[:6]}"
    with mock_aws():
        async with AioSession().create_client("sns", region_name=REGION) as sns:
            topic_arn = (
                await sns.create_topic(
                    Name=topic_name,
                    Attributes={"DisplayName": "test-topic"},
                    Tags=[
                        {"Key": "env", "Value": "dev"},
                        {"Key": "owner", "Value": "aiomoto"},
                    ],
                )
            )["TopicArn"]

            attrs = (await sns.get_topic_attributes(TopicArn=topic_arn))["Attributes"]
            tags = (await sns.list_tags_for_resource(ResourceArn=topic_arn))["Tags"]

    assert attrs["DisplayName"] == "test-topic"
    assert {tuple(t.items()) for t in tags} == {
        (("Key", "env"), ("Value", "dev")),
        (("Key", "owner"), ("Value", "aiomoto")),
    }


@pytest.mark.asyncio
async def test_publish_to_sqs_raw_async() -> None:
    with mock_aws():
        session = AioSession()
        async with (
            session.create_client("sns", region_name=REGION) as sns,
            session.create_client("sqs", region_name=REGION) as sqs,
        ):
            topic_arn = (await sns.create_topic(Name="some-topic"))["TopicArn"]
            queue_url = (await sqs.create_queue(QueueName="test-queue"))["QueueUrl"]
            queue_arn = (
                await sqs.get_queue_attributes(
                    QueueUrl=queue_url, AttributeNames=["QueueArn"]
                )
            )["Attributes"]["QueueArn"]

            subscription_arn = (
                await sns.subscribe(
                    TopicArn=topic_arn, Protocol="sqs", Endpoint=queue_arn
                )
            )["SubscriptionArn"]
            await sns.set_subscription_attributes(
                SubscriptionArn=subscription_arn,
                AttributeName="RawMessageDelivery",
                AttributeValue="true",
            )

            await sns.publish(TopicArn=topic_arn, Message="my message")
            received = await sqs.receive_message(
                QueueUrl=queue_url, MaxNumberOfMessages=1, WaitTimeSeconds=0
            )

    messages = received.get("Messages", [])
    assert len(messages) == 1
    assert messages[0]["Body"] == "my message"
