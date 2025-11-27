from __future__ import annotations

from typing import Any, TYPE_CHECKING

import aioboto3
from botocore.exceptions import ClientError
import pytest

from aiomoto import mock_aws


if TYPE_CHECKING:
    from aioboto3.client import ClientCreatorContext


BASIC_PIPELINE_KWARGS = {
    "PipelineName": "test",
    "MinUnits": 2,
    "MaxUnits": 4,
    "PipelineConfigurationBody": (
        'version: "2"\nopensearch-migration-pipeline:\n  source:\n    opensearch:\n'
        '      acknowledgments: true\n      hosts: ["https://vpc-test.eu-west-1.es.amazonaws.com"]\n'
        "      indices:\n        exclude:\n          - index_name_regex: '\\\\..*'\n"
        '      aws:\n        region: "eu-west-1"\n'
        '        sts_role_arn: "arn:aws:iam::123456789012:role/MyRole"\n'
        "        serverless: false\n  sink:\n    - opensearch:\n"
        '        hosts: ["https://kbjahvxo2jgx8beq2vob.eu-west-1.aoss.amazonaws.com"]\n'
        "        aws:\n"
        '          sts_role_arn: "arn:aws:iam::123456789012:role/MyRole"\n'
        '          region: "eu-west-1"\n          serverless: true\n'
    ),
}


def _client() -> ClientCreatorContext[Any]:
    return aioboto3.Session().client("osis", region_name="eu-west-1")


@pytest.mark.asyncio
async def test_create_pipeline_basic_async() -> None:
    with mock_aws():
        async with _client() as client:
            resp = (await client.create_pipeline(**BASIC_PIPELINE_KWARGS))["Pipeline"]

    assert resp["PipelineName"] == "test"
    assert resp["PipelineArn"] == "arn:aws:osis:eu-west-1:123456789012:pipeline/test"
    assert resp["MinUnits"] == 2
    assert resp["MaxUnits"] == 4
    assert resp["Status"] == "ACTIVE"
    assert resp["StatusReason"]["Description"] == (
        "The pipeline is ready to ingest data."
    )
    assert (
        resp["PipelineConfigurationBody"]
        == BASIC_PIPELINE_KWARGS["PipelineConfigurationBody"]
    )
    assert ".eu-west-1.osis.amazonaws.com" in resp["IngestEndpointUrls"][0]
    assert "test" in resp["IngestEndpointUrls"][0]
    assert resp["ServiceVpcEndpoints"][0]["ServiceName"] == "OPENSEARCH_SERVERLESS"
    assert resp["Destinations"][0]["ServiceName"] == "OpenSearch_Serverless"
    assert (
        resp["Destinations"][0]["Endpoint"]
        == "https://kbjahvxo2jgx8beq2vob.eu-west-1.aoss.amazonaws.com"
    )
    assert resp["Tags"] == []


@pytest.mark.asyncio
async def test_create_pipeline_extended_async() -> None:
    with mock_aws():
        kwargs = {
            "PipelineName": "test-2",
            "MinUnits": 2,
            "MaxUnits": 4,
            "PipelineConfigurationBody": (
                "version: '2'\n"
                "log-pipeline:\n"
                "  source:\n"
                "    kinesis:\n"
                "      stream_name: test\n"
                "  sink: []"
            ),
            "LogPublishingOptions": {
                "IsLoggingEnabled": True,
                "CloudWatchLogDestination": {"LogGroup": "/aws/osis/test"},
            },
            "BufferOptions": {"PersistentBufferEnabled": True},
            "EncryptionAtRestOptions": {
                "KmsKeyArn": (
                    "arn:aws:kms:eu-west-1:123456789012:key/"
                    "12345678-1234-1234-1234-123456789012"
                )
            },
            "Tags": [{"Key": "TestKey", "Value": "TestValue"}],
        }

    with mock_aws():
        async with _client() as client:
            resp = (await client.create_pipeline(**kwargs))["Pipeline"]

    assert resp["PipelineName"] == "test-2"
    assert "CreatedAt" in resp
    assert "LastUpdatedAt" in resp
    assert resp["LogPublishingOptions"]["IsLoggingEnabled"]
    assert (
        resp["LogPublishingOptions"]["CloudWatchLogDestination"]["LogGroup"]
        == "/aws/osis/test"
    )
    assert resp["BufferOptions"]["PersistentBufferEnabled"]
    assert (
        resp["EncryptionAtRestOptions"]["KmsKeyArn"]
        == "arn:aws:kms:eu-west-1:123456789012:key/12345678-1234-1234-1234-123456789012"
    )


@pytest.mark.asyncio
async def test_delete_pipeline_async() -> None:
    with mock_aws():
        async with _client() as client:
            resp = await client.create_pipeline(**BASIC_PIPELINE_KWARGS)
            arn = resp["Pipeline"]["PipelineArn"]

            await client.delete_pipeline(PipelineName="test")

            with pytest.raises(ClientError):  # pragma: no branch
                await client.get_pipeline(PipelineName="test")

    assert arn.endswith("/test")
