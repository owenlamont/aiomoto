from __future__ import annotations

import aioboto3
from botocore.exceptions import ClientError
from mypy_boto3_codebuild.type_defs import (
    ProjectArtifactsTypeDef,
    ProjectEnvironmentTypeDef,
    ProjectSourceTypeDef,
    TagTypeDef,
)
import pytest

from aiomoto import mock_aws


REGION = "eu-central-1"


def _session() -> aioboto3.Session:
    return aioboto3.Session()


def _env() -> ProjectEnvironmentTypeDef:
    return {
        "type": "LINUX_CONTAINER",
        "image": "contents_not_validated",
        "computeType": "BUILD_GENERAL1_SMALL",
    }


def _source_s3() -> ProjectSourceTypeDef:
    return {"type": "S3", "location": "bucketname/path/file.zip"}


def _artifacts_s3() -> ProjectArtifactsTypeDef:
    return {"type": "S3", "location": "bucketname"}


def _artifacts_none() -> ProjectArtifactsTypeDef:
    return {"type": "NO_ARTIFACTS"}


def _tags() -> list[TagTypeDef]:
    return [{"key": "k1", "value": "v1"}]


@mock_aws()
@pytest.mark.asyncio
async def test_codebuild_create_project_s3_artifacts_async() -> None:
    async with _session().client("codebuild", region_name=REGION) as client:
        project = (
            await client.create_project(
                name="some_project",
                source=_source_s3(),
                artifacts=_artifacts_s3(),
                environment=_env(),
                serviceRole=(
                    "arn:aws:iam::123456789012:role/service-role/"
                    "my-codebuild-service-role"
                ),
                tags=_tags(),
            )
        )["project"]

    assert project["name"] == "some_project"
    assert project["environment"] == _env()
    assert project["source"] == {"location": "bucketname/path/file.zip", "type": "S3"}
    assert project["artifacts"] == {"location": "bucketname", "type": "S3"}
    assert project["tags"] == [{"key": "k1", "value": "v1"}]


@pytest.mark.asyncio
async def test_codebuild_create_project_no_artifacts_async() -> None:
    with mock_aws():
        async with _session().client("codebuild", region_name=REGION) as client:
            project = (
                await client.create_project(
                    name="some_project",
                    source=_source_s3(),
                    artifacts=_artifacts_none(),
                    environment=_env(),
                    serviceRole=(
                        "arn:aws:iam::123456789012:role/service-role/"
                        "my-codebuild-service-role"
                    ),
                )
            )["project"]

    assert project["artifacts"] == {"type": "NO_ARTIFACTS"}
    assert project["source"]["type"] == "S3"


@pytest.mark.asyncio
async def test_codebuild_create_project_with_invalid_inputs_async() -> None:
    with mock_aws():
        async with _session().client("codebuild", region_name=REGION) as client:
            invalid_exc = client.exceptions.InvalidInputException

            with pytest.raises(invalid_exc):
                await client.create_project(
                    name=("some_project_" * 12),
                    source=_source_s3(),
                    artifacts=_artifacts_none(),
                    environment=_env(),
                    serviceRole="arn:aws:iam::123456789012:role/service-role/my-role",
                )

            with pytest.raises(invalid_exc):  # pragma: no branch
                await client.create_project(
                    name="!some_project_",
                    source=_source_s3(),
                    artifacts=_artifacts_none(),
                    environment=_env(),
                    serviceRole="arn:aws:iam::123456789012:role/service-role/my-role",
                )

            with pytest.raises(invalid_exc):  # pragma: no branch
                await client.create_project(
                    name="valid_name",
                    source=_source_s3(),
                    artifacts=_artifacts_none(),
                    environment=_env(),
                    serviceRole="arn:aws:iam::0000:role/service-role/my-role",
                )


@pytest.mark.asyncio
async def test_codebuild_create_project_when_exists_async() -> None:
    with mock_aws():
        async with _session().client("codebuild", region_name=REGION) as client:
            await client.create_project(
                name="some_project",
                source=_source_s3(),
                artifacts=_artifacts_none(),
                environment=_env(),
                serviceRole=(
                    "arn:aws:iam::123456789012:role/service-role/"
                    "my-codebuild-service-role"
                ),
            )

            with pytest.raises(ClientError) as err:  # pragma: no branch
                await client.create_project(
                    name="some_project",
                    source=_source_s3(),
                    artifacts=_artifacts_none(),
                    environment=_env(),
                    serviceRole=(
                        "arn:aws:iam::123456789012:role/service-role/"
                        "my-codebuild-service-role"
                    ),
                )

    assert err.value.response["Error"]["Code"] == "ResourceAlreadyExistsException"


@mock_aws()
@pytest.mark.asyncio
async def test_codebuild_list_projects_async() -> None:
    async with _session().client("codebuild", region_name=REGION) as client:
        await client.create_project(
            name="project1",
            source=_source_s3(),
            artifacts=_artifacts_s3(),
            environment=_env(),
            serviceRole=(
                "arn:aws:iam::123456789012:role/service-role/my-codebuild-service-role"
            ),
        )
        await client.create_project(
            name="project2",
            source=_source_s3(),
            artifacts=_artifacts_s3(),
            environment=_env(),
            serviceRole=(
                "arn:aws:iam::123456789012:role/service-role/my-codebuild-service-role"
            ),
        )
        await client.create_project(
            name="project3",
            source=_source_s3(),
            artifacts=_artifacts_s3(),
            environment=_env(),
            serviceRole=(
                "arn:aws:iam::123456789012:role/service-role/my-codebuild-service-role"
            ),
        )

        resp = await client.list_projects(sortBy="NAME", sortOrder="ASCENDING")

    assert resp["projects"] == ["project1", "project2", "project3"]
