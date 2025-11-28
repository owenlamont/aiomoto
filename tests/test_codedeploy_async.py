from __future__ import annotations

from typing import TYPE_CHECKING

import aioboto3
from botocore.exceptions import ClientError
import pytest

from aiomoto import mock_aws


if TYPE_CHECKING:
    from aioboto3.client import ClientCreatorContext
    from types_aiobotocore_codedeploy.client import CodeDeployClient


REGION = "us-west-2"
ACCOUNT_ARN_ROOT = "arn:aws:codedeploy"


def _session() -> aioboto3.Session:
    return aioboto3.Session()


def _client(region: str = REGION) -> ClientCreatorContext[CodeDeployClient]:
    return _session().client("codedeploy", region_name=region)


def _service_role() -> str:
    return "arn:aws:iam::123456789012:role/CodeDeployDemoRole"


def _s3_revision() -> dict[str, object]:
    return {
        "revisionType": "S3",
        "s3Location": {
            "bucket": "my-bucket",
            "key": "my-key",
            "bundleType": "zip",
            "version": "1",
            "eTag": "my-etag",
        },
    }


@mock_aws()
@pytest.mark.asyncio
async def test_create_application_async() -> None:
    async with _client("ap-southeast-1") as client:
        for platform in ["Server", "Lambda", "ECS"]:
            name = f"test-application-{platform}"
            response = await client.create_application(
                applicationName=name,
                computePlatform=platform,
                tags=[{"Key": "Name", "Value": "Test"}],
            )
            assert "applicationId" in response

            resp = await client.get_application(applicationName=name)
            application = resp["application"]
            assert application["applicationId"] == response["applicationId"]
            assert application["applicationName"] == name
            assert application["computePlatform"] == platform
            assert "createTime" in application


@pytest.mark.asyncio
async def test_create_application_existing_async() -> None:
    with mock_aws():
        async with _client("ap-southeast-1") as client:
            first = await client.create_application(
                applicationName="sample_app", computePlatform="Server"
            )
            assert "applicationId" in first

            with pytest.raises(ClientError) as exc:  # pragma: no branch
                await client.create_application(
                    applicationName="sample_app", computePlatform="Server"
                )

    assert exc.value.response["Error"]["Code"] == "ApplicationAlreadyExistsException"


@pytest.mark.asyncio
async def test_create_deployment_revision_s3_async() -> None:
    with mock_aws():
        async with _client("us-west-2") as client:
            application_name = "mytestapp"
            deployment_group_name = "test-deployment-group"

            await client.create_application(
                applicationName=application_name, computePlatform="Server"
            )
            await client.create_deployment_group(
                applicationName=application_name,
                deploymentGroupName=deployment_group_name,
                serviceRoleArn=_service_role(),
            )

            revision = _s3_revision()
            response = await client.create_deployment(
                applicationName=application_name,
                deploymentGroupName=deployment_group_name,
                revision=revision,
                description="Test deployment",
            )
            deployment_id = response["deploymentId"]

            deployment = await client.get_deployment(deploymentId=deployment_id)
            info = deployment["deploymentInfo"]
            assert info["applicationName"] == application_name
            assert info["revision"]["revisionType"] == "S3"
            assert info["revision"]["s3Location"] == revision["s3Location"]
            assert info["status"] == "Created"
            assert "createTime" in info


@pytest.mark.asyncio
async def test_create_deployment_nonexistent_group_async() -> None:
    with mock_aws():
        async with _client("eu-west-1") as client:
            application_name = "mytestapp"
            await client.create_application(
                applicationName=application_name, computePlatform="Lambda"
            )

            with pytest.raises(ClientError) as exc:  # pragma: no branch
                await client.create_deployment(
                    applicationName=application_name,
                    deploymentGroupName="non-existent-group-name",
                    revision=_s3_revision(),
                )

    assert exc.value.response["Error"]["Code"] == "DeploymentGroupDoesNotExistException"


@pytest.mark.asyncio
async def test_create_deployment_group_async() -> None:
    with mock_aws():
        async with _client("eu-west-1") as client:
            application_name = "mytestapp"
            deployment_group_name = "mytestdeploymentgroup"

            await client.create_application(
                applicationName=application_name, computePlatform="Lambda"
            )

            response = await client.create_deployment_group(
                applicationName=application_name,
                deploymentGroupName=deployment_group_name,
                serviceRoleArn=_service_role(),
            )

    assert "deploymentGroupId" in response


@pytest.mark.asyncio
async def test_create_deployment_group_existing_async() -> None:
    with mock_aws():
        async with _client("eu-west-1") as client:
            application_name = "mytestapp"
            deployment_group_name = "mytestdeploymentgroup"

            await client.create_application(
                applicationName=application_name, computePlatform="Lambda"
            )

            await client.create_deployment_group(
                applicationName=application_name,
                deploymentGroupName=deployment_group_name,
                serviceRoleArn=_service_role(),
            )

            with pytest.raises(ClientError) as exc:  # pragma: no branch
                await client.create_deployment_group(
                    applicationName=application_name,
                    deploymentGroupName=deployment_group_name,
                    serviceRoleArn=_service_role(),
                )

    assert (
        exc.value.response["Error"]["Code"] == "DeploymentGroupAlreadyExistsException"
    )


@pytest.mark.asyncio
async def test_get_deployment_async() -> None:
    with mock_aws():
        async with _client("eu-west-1") as client:
            application_name = "mytestapp"
            deployment_group_name = "mytestdeploymentgroup"
            revision_content = "test-content"
            revision_sha256 = "test-sha256"

            await client.create_application(
                applicationName=application_name, computePlatform="Lambda"
            )
            await client.create_deployment_group(
                applicationName=application_name,
                deploymentGroupName=deployment_group_name,
                serviceRoleArn=_service_role(),
            )
            deployment_response = await client.create_deployment(
                applicationName=application_name,
                deploymentGroupName=deployment_group_name,
                description="Test deployment",
                revision={
                    "revisionType": "String",
                    "string": {"content": revision_content, "sha256": revision_sha256},
                },
            )
            deployment_id = deployment_response["deploymentId"]

            response = await client.get_deployment(deploymentId=deployment_id)

    info = response["deploymentInfo"]
    assert info["deploymentId"] == deployment_id
    assert info["applicationName"] == application_name
    assert info["deploymentGroupName"] == deployment_group_name
    assert info["description"] == "Test deployment"
    assert info["revision"]["revisionType"] == "String"
    assert info["revision"]["string"]["content"] == revision_content
    assert info["revision"]["string"]["sha256"] == revision_sha256
    assert info["status"] == "Created"
    assert "createTime" in info


@pytest.mark.asyncio
async def test_batch_get_applications_async() -> None:
    with mock_aws():
        async with _client("us-east-2") as client:
            await client.create_application(
                applicationName="sample_app1", computePlatform="Lambda"
            )
            await client.create_application(
                applicationName="sample_app2", computePlatform="Server"
            )
            await client.create_application(
                applicationName="sample_app3", computePlatform="ECS"
            )

            resp = await client.batch_get_applications(
                applicationNames=["sample_app1", "sample_app2", "sample_app3"]
            )

    assert len(resp["applicationsInfo"]) == 3


@pytest.mark.asyncio
async def test_list_applications_async() -> None:
    with mock_aws():
        async with _client("us-east-2") as client:
            resp = await client.list_applications()
            assert resp["applications"] == []

            await client.create_application(
                applicationName="sample_app", computePlatform="Server"
            )
            await client.create_application(
                applicationName="sample_app2", computePlatform="Server"
            )
            resp = await client.list_applications()

    assert set(resp["applications"]) == {"sample_app", "sample_app2"}


@pytest.mark.asyncio
async def test_list_deployments_async() -> None:
    with mock_aws():
        async with _client("ap-southeast-1") as client:
            application_name = "mytestapp"
            dg1 = "mytestdeploymentgroup"
            dg2 = "mytestdeploymentgroup2"

            empty = await client.list_deployments()
            assert empty["deployments"] == []

            await client.create_application(
                applicationName=application_name, computePlatform="Server"
            )
            await client.create_deployment_group(
                applicationName=application_name,
                deploymentGroupName=dg1,
                serviceRoleArn=_service_role(),
            )
            await client.create_deployment_group(
                applicationName=application_name,
                deploymentGroupName=dg2,
                serviceRoleArn=_service_role(),
            )
            await client.create_deployment(
                applicationName=application_name,
                deploymentGroupName=dg1,
                revision=_s3_revision(),
            )
            await client.create_deployment(
                applicationName=application_name,
                deploymentGroupName=dg2,
                revision=_s3_revision(),
            )

            resp = await client.list_deployments()

    assert len(resp["deployments"]) == 2
