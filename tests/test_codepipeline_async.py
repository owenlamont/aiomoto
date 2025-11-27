from collections.abc import Mapping
from copy import deepcopy
from datetime import datetime
import json
from typing import TYPE_CHECKING

import aioboto3
from botocore.exceptions import ClientError
import pytest

from aiomoto import mock_aws


if TYPE_CHECKING:
    from aioboto3.client import ClientCreatorContext
    from types_aiobotocore_codepipeline.client import CodePipelineClient
    from types_aiobotocore_codepipeline.type_defs import (
        CreatePipelineOutputTypeDef,
        PipelineDeclarationTypeDef,
        TagTypeDef,
    )
    from types_aiobotocore_iam.client import IAMClient


REGION = "us-east-1"
ACCOUNT_ID = "123456789012"
PIPELINE_ARN = f"arn:aws:codepipeline:{REGION}:{ACCOUNT_ID}:test-pipeline"


def _session() -> aioboto3.Session:
    return aioboto3.Session()


def _client(region: str = REGION) -> "ClientCreatorContext[CodePipelineClient]":
    return _session().client("codepipeline", region_name=region)


def _iam_client() -> "ClientCreatorContext[IAMClient]":
    return _session().client("iam", region_name=REGION)


def _simple_trust_policy() -> Mapping[str, object]:
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Service": "codepipeline.amazonaws.com"},
                "Action": "sts:AssumeRole",
            }
        ],
    }


def _extended_trust_policy() -> Mapping[str, object]:
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Service": "codebuild.amazonaws.com"},
                "Action": "sts:AssumeRole",
            },
            {
                "Effect": "Allow",
                "Principal": {"Service": "codepipeline.amazonaws.com"},
                "Action": "sts:AssumeRole",
            },
        ],
    }


async def _get_role_arn(
    name: str = "test-role", trust_policy: Mapping[str, object] | None = None
) -> str:
    if trust_policy is None:
        trust_policy = _simple_trust_policy()
    async with _iam_client() as iam:
        try:
            role_arn: str = (await iam.get_role(RoleName=name))["Role"]["Arn"]
            return role_arn
        except ClientError:
            created = await iam.create_role(
                RoleName=name, AssumeRolePolicyDocument=json.dumps(trust_policy)
            )
            return str(created["Role"]["Arn"])


def _expected_pipeline(role_arn: str) -> "PipelineDeclarationTypeDef":
    return {
        "name": "test-pipeline",
        "roleArn": role_arn,
        "artifactStore": {
            "type": "S3",
            "location": "codepipeline-us-east-1-123456789012",
        },
        "stages": [
            {
                "name": "Stage-1",
                "actions": [
                    {
                        "name": "Action-1",
                        "actionTypeId": {
                            "category": "Source",
                            "owner": "AWS",
                            "provider": "S3",
                            "version": "1",
                        },
                        "runOrder": 1,
                        "configuration": {
                            "S3Bucket": "test-bucket",
                            "S3ObjectKey": "test-object",
                        },
                        "outputArtifacts": [{"name": "artifact"}],
                        "inputArtifacts": [],
                    }
                ],
            },
            {
                "name": "Stage-2",
                "actions": [
                    {
                        "name": "Action-1",
                        "actionTypeId": {
                            "category": "Approval",
                            "owner": "AWS",
                            "provider": "Manual",
                            "version": "1",
                        },
                        "runOrder": 1,
                        "configuration": {},
                        "outputArtifacts": [],
                        "inputArtifacts": [],
                    }
                ],
            },
        ],
        "version": 1,
    }


async def _create_basic_codepipeline(
    client: "CodePipelineClient",
    name: str,
    role_arn: str,
    tags: list["TagTypeDef"] | None = None,
) -> "CreatePipelineOutputTypeDef":
    if tags is None:
        tags = [{"key": "key", "value": "value"}]
    pipeline: PipelineDeclarationTypeDef = deepcopy(_expected_pipeline(role_arn))
    pipeline["name"] = name
    return await client.create_pipeline(pipeline=pipeline, tags=tags)


@mock_aws()
@pytest.mark.asyncio
async def test_create_pipeline_async() -> None:
    async with _client() as client:
        role_arn = await _get_role_arn()
        response = await _create_basic_codepipeline(client, "test-pipeline", role_arn)

    assert response["pipeline"] == _expected_pipeline(role_arn)
    assert response["tags"] == [{"key": "key", "value": "value"}]


@pytest.mark.asyncio
async def test_create_pipeline_errors_async() -> None:
    with mock_aws():
        async with _client() as client:
            role_arn = await _get_role_arn()
            await _create_basic_codepipeline(client, "test-pipeline", role_arn)

            with pytest.raises(ClientError) as e1:
                await _create_basic_codepipeline(client, "test-pipeline", role_arn)

            with pytest.raises(ClientError) as e2:
                await client.create_pipeline(
                    pipeline={
                        "name": "invalid-pipeline",
                        "roleArn": "arn:aws:iam::123456789012:role/not-existing",
                        "artifactStore": {
                            "type": "S3",
                            "location": "codepipeline-us-east-1-123456789012",
                        },
                        "stages": [
                            {
                                "name": "Stage-1",
                                "actions": [
                                    {
                                        "name": "Action-1",
                                        "actionTypeId": {
                                            "category": "Source",
                                            "owner": "AWS",
                                            "provider": "S3",
                                            "version": "1",
                                        },
                                        "runOrder": 1,
                                    }
                                ],
                            }
                        ],
                    }
                )

            bad_role = await _get_role_arn(
                name="wrong-role",
                trust_policy={
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Effect": "Allow",
                            "Principal": {"Service": "s3.amazonaws.com"},
                            "Action": "sts:AssumeRole",
                        }
                    ],
                },
            )
            with pytest.raises(ClientError) as e3:
                await client.create_pipeline(
                    pipeline={
                        "name": "invalid-pipeline",
                        "roleArn": bad_role,
                        "artifactStore": {
                            "type": "S3",
                            "location": "codepipeline-us-east-1-123456789012",
                        },
                        "stages": [
                            {
                                "name": "Stage-1",
                                "actions": [
                                    {
                                        "name": "Action-1",
                                        "actionTypeId": {
                                            "category": "Source",
                                            "owner": "AWS",
                                            "provider": "S3",
                                            "version": "1",
                                        },
                                        "runOrder": 1,
                                    }
                                ],
                            }
                        ],
                    }
                )

            with pytest.raises(ClientError) as e4:
                await client.create_pipeline(
                    pipeline={
                        "name": "invalid-pipeline",
                        "roleArn": role_arn,
                        "artifactStore": {
                            "type": "S3",
                            "location": "codepipeline-us-east-1-123456789012",
                        },
                        "stages": [
                            {
                                "name": "Stage-1",
                                "actions": [
                                    {
                                        "name": "Action-1",
                                        "actionTypeId": {
                                            "category": "Source",
                                            "owner": "AWS",
                                            "provider": "S3",
                                            "version": "1",
                                        },
                                        "runOrder": 1,
                                        "configuration": {
                                            "S3Bucket": "test-bucket",
                                            "S3ObjectKey": "test-object",
                                        },
                                        "outputArtifacts": [{"name": "artifact"}],
                                    }
                                ],
                            }
                        ],
                    }
                )

    assert e1.value.response["Error"]["Code"] == "InvalidStructureException"
    assert e2.value.response["Error"]["Code"] == "InvalidStructureException"
    assert e3.value.response["Error"]["Code"] == "InvalidStructureException"
    assert e4.value.response["Error"]["Code"] == "InvalidStructureException"


@pytest.mark.asyncio
async def test_get_pipeline_async() -> None:
    with mock_aws():
        async with _client() as client:
            role_arn = await _get_role_arn()
            await _create_basic_codepipeline(client, "test-pipeline", role_arn)
            response = await client.get_pipeline(name="test-pipeline")

    assert response["pipeline"] == _expected_pipeline(role_arn)
    assert response["metadata"]["pipelineArn"] == PIPELINE_ARN
    assert isinstance(response["metadata"]["created"], datetime)
    assert isinstance(response["metadata"]["updated"], datetime)


@pytest.mark.asyncio
async def test_update_pipeline_async() -> None:
    metadata_after: dict[str, object] | None = None
    with mock_aws():
        async with _client() as client:
            role_arn = await _get_role_arn()
            await _create_basic_codepipeline(client, "test-pipeline", role_arn)
            before = await client.get_pipeline(name="test-pipeline")
            created_time = before["metadata"]["created"]
            updated_time = before["metadata"]["updated"]

            response = await client.update_pipeline(
                pipeline={
                    "name": "test-pipeline",
                    "roleArn": role_arn,
                    "artifactStore": {
                        "type": "S3",
                        "location": "codepipeline-us-east-1-123456789012",
                    },
                    "stages": [
                        {
                            "name": "Stage-1",
                            "actions": [
                                {
                                    "name": "Action-1",
                                    "actionTypeId": {
                                        "category": "Source",
                                        "owner": "AWS",
                                        "provider": "S3",
                                        "version": "1",
                                    },
                                    "configuration": {
                                        "S3Bucket": "different-bucket",
                                        "S3ObjectKey": "test-object",
                                    },
                                    "outputArtifacts": [{"name": "artifact"}],
                                }
                            ],
                        },
                        {
                            "name": "Stage-2",
                            "actions": [
                                {
                                    "name": "Action-1",
                                    "actionTypeId": {
                                        "category": "Approval",
                                        "owner": "AWS",
                                        "provider": "Manual",
                                        "version": "1",
                                    },
                                    "runOrder": 1,
                                    "configuration": {},
                                    "outputArtifacts": [],
                                    "inputArtifacts": [],
                                }
                            ],
                        },
                    ],
                }
            )
            metadata_after = (await client.get_pipeline(name="test-pipeline"))[
                "metadata"
            ]

    expected = deepcopy(_expected_pipeline(role_arn))
    expected["stages"][0]["actions"][0]["configuration"] = {
        "S3Bucket": "different-bucket",
        "S3ObjectKey": "test-object",
    }
    expected["version"] = 2
    assert response["pipeline"] == expected
    assert created_time == before["metadata"]["created"]
    assert response["pipeline"]["version"] == 2
    assert metadata_after is not None
    assert metadata_after["updated"] > updated_time


@pytest.mark.asyncio
async def test_list_pipelines_async() -> None:
    with mock_aws():
        async with _client() as client:
            role_arn = await _get_role_arn()
            await _create_basic_codepipeline(client, "test-pipeline-1", role_arn)
            await _create_basic_codepipeline(client, "test-pipeline-2", role_arn)

            response = await client.list_pipelines()

    assert {p["name"] for p in response["pipelines"]} == {
        "test-pipeline-1",
        "test-pipeline-2",
    }
    assert all(isinstance(p["created"], datetime) for p in response["pipelines"])
    assert all(isinstance(p["updated"], datetime) for p in response["pipelines"])


@pytest.mark.asyncio
async def test_delete_pipeline_async() -> None:
    with mock_aws():
        async with _client() as client:
            role_arn = await _get_role_arn()
            await _create_basic_codepipeline(client, "test-pipeline", role_arn)
            assert len((await client.list_pipelines())["pipelines"]) == 1

            await client.delete_pipeline(name="test-pipeline")
            after = await client.list_pipelines()
            await client.delete_pipeline(name="test-pipeline")  # idempotent

    assert after["pipelines"] == []


@pytest.mark.asyncio
async def test_tagging_resource_async() -> None:
    with mock_aws():
        async with _client() as client:
            role_arn = await _get_role_arn()
            await _create_basic_codepipeline(client, "test-pipeline", role_arn)

            await client.tag_resource(
                resourceArn=PIPELINE_ARN, tags=[{"key": "key-2", "value": "value-2"}]
            )

            response = await client.list_tags_for_resource(resourceArn=PIPELINE_ARN)

    assert response["tags"] == [
        {"key": "key", "value": "value"},
        {"key": "key-2", "value": "value-2"},
    ]


@pytest.mark.asyncio
async def test_untag_resource_async() -> None:
    with mock_aws():
        async with _client() as client:
            role_arn = await _get_role_arn()
            await _create_basic_codepipeline(client, "test-pipeline", role_arn)

            await client.untag_resource(resourceArn=PIPELINE_ARN, tagKeys=["key"])
            response = await client.list_tags_for_resource(resourceArn=PIPELINE_ARN)
            await client.untag_resource(resourceArn=PIPELINE_ARN, tagKeys=["key"])

    assert response["tags"] == []


@pytest.mark.asyncio
async def test_create_pipeline_with_extended_trust_policy_async() -> None:
    with mock_aws():
        async with _client() as client:
            role_arn = await _get_role_arn(
                name="test-role-extended", trust_policy=_extended_trust_policy()
            )
            response = await _create_basic_codepipeline(
                client, "test-pipeline", role_arn=role_arn
            )

    expected = deepcopy(_expected_pipeline(role_arn))
    expected["roleArn"] = role_arn
    assert response["pipeline"] == expected
    assert response["tags"] == [{"key": "key", "value": "value"}]


@pytest.mark.asyncio
async def test_list_tags_for_resource_errors_async() -> None:
    with mock_aws():
        async with _client() as client:
            with pytest.raises(ClientError) as e:
                await client.list_tags_for_resource(
                    resourceArn="arn:aws:codepipeline:us-east-1:123456789012:not-existing"
                )

    ex = e.value
    assert ex.response["Error"]["Code"] == "ResourceNotFoundException"
