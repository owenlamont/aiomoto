from typing import Any, TYPE_CHECKING

import aioboto3
import pytest

from aiomoto import mock_aws


if TYPE_CHECKING:
    from aioboto3.client import ClientCreatorContext


def _client() -> ClientCreatorContext[Any]:
    return aioboto3.Session().client("elasticache", region_name="us-east-1")


@pytest.mark.asyncio
async def test_create_cache_cluster_async() -> None:
    with mock_aws():
        async with _client() as client:
            resp = await client.create_cache_cluster(
                CacheClusterId="cluster-1",
                Engine="redis",
                CacheNodeType="cache.t3.micro",
                NumCacheNodes=1,
            )

            cluster = resp["CacheCluster"]
            assert cluster["CacheClusterId"] == "cluster-1"
            assert cluster["Engine"] == "redis"

            listed = await client.describe_cache_clusters(CacheClusterId="cluster-1")

    assert listed["CacheClusters"][0]["CacheClusterId"] == "cluster-1"


@pytest.mark.asyncio
async def test_create_replication_group_async() -> None:
    with mock_aws():
        async with _client() as client:
            resp = await client.create_replication_group(
                ReplicationGroupId="rg1",
                ReplicationGroupDescription="desc",
                Engine="redis",
                CacheNodeType="cache.t3.micro",
                NumNodeGroups=1,
                ReplicasPerNodeGroup=1,
            )

            group = resp["ReplicationGroup"]
            assert group["ReplicationGroupId"] == "rg1"

            described = await client.describe_replication_groups(
                ReplicationGroupId="rg1"
            )

    assert described["ReplicationGroups"][0]["Status"] in {"creating", "available"}
