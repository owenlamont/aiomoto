from typing import Any, TYPE_CHECKING

import aioboto3
import pytest

from aiomoto import mock_aws


if TYPE_CHECKING:
    from aioboto3.client import ClientCreatorContext


DEFAULT_REGION = "us-east-1"


def _client(region: str = DEFAULT_REGION) -> ClientCreatorContext[Any]:
    return aioboto3.Session().client("bedrock", region_name=region)


def _s3(region: str = DEFAULT_REGION) -> ClientCreatorContext[Any]:
    return aioboto3.Session().client("s3", region_name=region)


@pytest.mark.asyncio
async def test_create_model_customization_job_async() -> None:
    with mock_aws():
        async with _client() as client, _s3() as s3:
            await s3.create_bucket(Bucket="training_bucket")
            await s3.create_bucket(Bucket="output_bucket")

            resp = await client.create_model_customization_job(
                jobName="testjob",
                customModelName="testmodel",
                roleArn="testrole",
                baseModelIdentifier="anthropic.claude-3-sonnet-20240229-v1:0",
                trainingDataConfig={"s3Uri": "s3://training_bucket"},
                outputDataConfig={"s3Uri": "s3://output_bucket"},
                hyperParameters={"learning_rate": "0.01"},
            )

    assert resp["jobArn"].endswith("model-customization-job/testjob")


@pytest.mark.asyncio
async def test_get_model_invocation_logging_configuration_async() -> None:
    logging_config = {
        "cloudWatchConfig": {
            "logGroupName": "Test",
            "roleArn": "testrole",
            "largeDataDeliveryS3Config": {"bucketName": "testbucket"},
        },
        "s3Config": {"bucketName": "configbucket"},
    }

    with mock_aws():
        async with _client() as client:
            await client.put_model_invocation_logging_configuration(
                loggingConfig=logging_config
            )
            resp = await client.get_model_invocation_logging_configuration()

    assert resp["loggingConfig"]["cloudWatchConfig"]["logGroupName"] == "Test"


@pytest.mark.asyncio
async def test_tag_and_untag_resource_async() -> None:
    with mock_aws():
        async with _client() as client, _s3() as s3:
            await s3.create_bucket(Bucket="training_bucket")
            await s3.create_bucket(Bucket="output_bucket")
            job = await client.create_model_customization_job(
                jobName="testjob",
                customModelName="testmodel",
                roleArn="testrole",
                baseModelIdentifier="anthropic.claude-3-sonnet-20240229-v1:0",
                trainingDataConfig={"s3Uri": "s3://training_bucket"},
                outputDataConfig={"s3Uri": "s3://output_bucket"},
                hyperParameters={"learning_rate": "0.01"},
            )

            await client.tag_resource(
                resourceARN=job["jobArn"],
                tags=[{"key": "k1", "value": "v1"}, {"key": "k2", "value": "v2"}],
            )
            await client.untag_resource(resourceARN=job["jobArn"], tagKeys=["k1"])
            tags = await client.list_tags_for_resource(resourceARN=job["jobArn"])

    assert {t["key"] for t in tags["tags"]} == {"k2"}
