from uuid import uuid4

import aioboto3
import pytest

from aiomoto import mock_aws


REGION = "us-east-1"
ACCOUNT_ID = "123456789012"


def _session() -> aioboto3.Session:
    return aioboto3.Session()


@pytest.mark.asyncio
async def test_create_and_delete_topic_async() -> None:
    topic_name = f"topic-{uuid4().hex[:6]}"
    with mock_aws():
        async with _session().client("sns", region_name=REGION) as sns:
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
        async with _session().client("sns", region_name=REGION) as sns:
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
        async with (
            _session().resource("sns", region_name=REGION) as sns_res,
            _session().resource("sqs", region_name=REGION) as sqs_res,
        ):
            topic = await sns_res.create_topic(Name="some-topic")
            queue = await sqs_res.create_queue(QueueName="test-queue")

            queue_arn = (await queue.attributes)["QueueArn"]
            subscription = await topic.subscribe(Protocol="sqs", Endpoint=queue_arn)
            await subscription.set_attributes(
                AttributeName="RawMessageDelivery", AttributeValue="true"
            )

            await topic.publish(Message="my message")
            messages = await queue.receive_messages(
                MaxNumberOfMessages=1, WaitTimeSeconds=0
            )

    assert len(messages) == 1
    assert await messages[0].body == "my message"
