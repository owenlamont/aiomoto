from __future__ import annotations

from typing import Any, TYPE_CHECKING

import aioboto3
from botocore.exceptions import ClientError
import pytest

from aiomoto import mock_aws


if TYPE_CHECKING:
    from aioboto3.client import ClientCreatorContext


def _client(region: str = "eu-west-1") -> ClientCreatorContext[Any]:
    return aioboto3.Session().client("mediastore", region_name=region)


@pytest.mark.asyncio
async def test_create_container_succeeds() -> None:
    with mock_aws():
        async with _client() as client:
            response = await client.create_container(
                ContainerName="Awesome container!", Tags=[{"Key": "customer"}]
            )

    assert response["ResponseMetadata"]["HTTPStatusCode"] == 200
    container = response["Container"]
    assert container["ARN"] == f"arn:aws:mediastore:container:{container['Name']}"
    assert container["Name"] == "Awesome container!"
    assert container["Status"] == "CREATING"


@pytest.mark.asyncio
async def test_describe_container_succeeds() -> None:
    with mock_aws():
        async with _client() as client:
            name = "Awesome container!"
            await client.create_container(
                ContainerName=name, Tags=[{"Key": "customer"}]
            )

            response = await client.describe_container(ContainerName=name)

    assert response["ResponseMetadata"]["HTTPStatusCode"] == 200
    container = response["Container"]
    assert container["ARN"] == f"arn:aws:mediastore:container:{name}"
    assert container["Name"] == name
    assert container["Status"] == "ACTIVE"


@pytest.mark.asyncio
async def test_list_containers_succeeds() -> None:
    with mock_aws():
        async with _client() as client:
            name = "Awesome container!"
            await client.create_container(
                ContainerName=name, Tags=[{"Key": "customer"}]
            )
            containers = (await client.list_containers())["Containers"]
            assert len(containers) == 1

            await client.create_container(
                ContainerName=f"{name}2", Tags=[{"Key": "customer"}]
            )
            containers = (await client.list_containers())["Containers"]

    assert len(containers) == 2


@pytest.mark.asyncio
async def test_describe_container_missing() -> None:
    with mock_aws():
        async with _client() as client:
            with pytest.raises(ClientError):  # pragma: no branch
                await client.describe_container(ContainerName="container-name")


@pytest.mark.asyncio
async def test_put_lifecycle_policy_roundtrip() -> None:
    with mock_aws():
        async with _client() as client:
            name = "container-name"
            await client.create_container(
                ContainerName=name, Tags=[{"Key": "customer"}]
            )

            await client.put_lifecycle_policy(
                ContainerName=name, LifecyclePolicy="lifecycle-policy"
            )
            response = await client.get_lifecycle_policy(ContainerName=name)

    assert response["ResponseMetadata"]["HTTPStatusCode"] == 200
    assert response["LifecyclePolicy"] == "lifecycle-policy"


@pytest.mark.asyncio
async def test_put_lifecycle_policy_missing_container() -> None:
    with mock_aws():
        async with _client() as client:
            with pytest.raises(ClientError):  # pragma: no branch
                await client.put_lifecycle_policy(
                    ContainerName="name", LifecyclePolicy="policy"
                )


@pytest.mark.asyncio
async def test_get_lifecycle_policy_missing_container() -> None:
    with mock_aws():
        async with _client() as client:
            with pytest.raises(ClientError):  # pragma: no branch
                await client.get_lifecycle_policy(ContainerName="container-name")


@pytest.mark.asyncio
async def test_get_lifecycle_policy_missing_policy() -> None:
    with mock_aws():
        async with _client() as client:
            await client.create_container(
                ContainerName="container-name", Tags=[{"Key": "customer"}]
            )
            with pytest.raises(ClientError):  # pragma: no branch
                await client.get_lifecycle_policy(ContainerName="container-name")


@pytest.mark.asyncio
async def test_put_container_policy_roundtrip() -> None:
    with mock_aws():
        async with _client() as client:
            name = "container-name"
            await client.create_container(ContainerName=name)

            await client.put_container_policy(
                ContainerName=name, Policy="container-policy"
            )
            response = await client.get_container_policy(ContainerName=name)

    assert response["ResponseMetadata"]["HTTPStatusCode"] == 200
    assert response["Policy"] == "container-policy"


@pytest.mark.asyncio
async def test_put_container_policy_missing_container() -> None:
    with mock_aws():
        async with _client() as client:
            with pytest.raises(ClientError):  # pragma: no branch
                await client.put_container_policy(ContainerName="name", Policy="policy")


@pytest.mark.asyncio
async def test_get_container_policy_missing_container() -> None:
    with mock_aws():
        async with _client() as client:
            with pytest.raises(ClientError):  # pragma: no branch
                await client.get_container_policy(ContainerName="container-name")


@pytest.mark.asyncio
async def test_get_container_policy_missing_policy() -> None:
    with mock_aws():
        async with _client() as client:
            await client.create_container(
                ContainerName="container-name", Tags=[{"Key": "customer"}]
            )
            with pytest.raises(ClientError):  # pragma: no branch
                await client.get_container_policy(ContainerName="container-name")


@pytest.mark.asyncio
async def test_put_metric_policy_roundtrip() -> None:
    with mock_aws():
        async with _client() as client:
            name = "container-name"
            await client.create_container(ContainerName=name)
            await client.put_metric_policy(
                ContainerName=name, MetricPolicy={"ContainerLevelMetrics": "ENABLED"}
            )
            response = await client.get_metric_policy(ContainerName=name)

    assert response["ResponseMetadata"]["HTTPStatusCode"] == 200
    assert response["MetricPolicy"] == {"ContainerLevelMetrics": "ENABLED"}


@pytest.mark.asyncio
async def test_put_metric_policy_missing_container() -> None:
    with mock_aws():
        async with _client() as client:
            with pytest.raises(ClientError):  # pragma: no branch
                await client.put_metric_policy(
                    ContainerName="container-name",
                    MetricPolicy={"ContainerLevelMetrics": "ENABLED"},
                )


@pytest.mark.asyncio
async def test_get_metric_policy_missing_container() -> None:
    with mock_aws():
        async with _client() as client:
            with pytest.raises(ClientError):  # pragma: no branch
                await client.get_metric_policy(ContainerName="container-name")


@pytest.mark.asyncio
async def test_get_metric_policy_missing_policy() -> None:
    with mock_aws():
        async with _client() as client:
            await client.create_container(
                ContainerName="container-name", Tags=[{"Key": "customer"}]
            )
            with pytest.raises(ClientError):  # pragma: no branch
                await client.get_metric_policy(ContainerName="container-name")


@pytest.mark.asyncio
async def test_list_tags_for_resource() -> None:
    tags = [{"Key": "customer"}]
    with mock_aws():
        async with _client() as client:
            name = "Awesome container!"
            await client.create_container(ContainerName=name, Tags=tags)

            response = await client.list_tags_for_resource(Resource=name)

    assert response["ResponseMetadata"]["HTTPStatusCode"] == 200
    assert response["Tags"] == tags


@pytest.mark.asyncio
async def test_list_tags_for_resource_none() -> None:
    with mock_aws():
        async with _client() as client:
            name = "Awesome container!"
            await client.create_container(ContainerName=name)

            response = await client.list_tags_for_resource(Resource=name)

    assert response["ResponseMetadata"]["HTTPStatusCode"] == 200
    assert response.get("Tags") is None
