from typing import Any, TYPE_CHECKING

import aioboto3
import pytest

from aiomoto import mock_aws


if TYPE_CHECKING:
    from aioboto3.client import ClientCreatorContext


def _client() -> ClientCreatorContext[Any]:
    return aioboto3.Session().client("cloudhsmv2", region_name="us-east-1")


@pytest.mark.asyncio
async def test_create_cluster_async() -> None:
    with mock_aws():
        async with _client() as client:
            resp = await client.create_cluster(
                SubnetIds=["subnet-12345"], HsmType="hsm1.medium"
            )

    assert resp["Cluster"]["State"] in {"UNINITIALIZED", "ACTIVE"}


@pytest.mark.asyncio
async def test_describe_clusters_async() -> None:
    with mock_aws():
        async with _client() as client:
            await client.create_cluster(
                SubnetIds=["subnet-12345"], HsmType="hsm1.medium"
            )
            resp = await client.describe_clusters()

    assert len(resp.get("Clusters", [])) == 1
