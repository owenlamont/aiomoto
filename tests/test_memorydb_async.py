from typing import Any, TYPE_CHECKING

import aioboto3
from botocore.exceptions import ClientError
import pytest

from aiomoto import mock_aws


REGION = "ap-southeast-1"

if TYPE_CHECKING:
    from aioboto3.client import ClientCreatorContext


def _client(region: str = REGION) -> "ClientCreatorContext[Any]":
    return aioboto3.Session().client("memorydb", region_name=region)


async def _create_subnet_group(region: str) -> dict[str, Any]:
    async with aioboto3.Session().resource("ec2", region_name=region) as ec2:
        vpc = await ec2.create_vpc(CidrBlock="10.0.0.0/16")
        subnet1 = await ec2.create_subnet(VpcId=vpc.id, CidrBlock="10.0.0.0/24")
        subnet2 = await ec2.create_subnet(VpcId=vpc.id, CidrBlock="10.0.1.0/24")
    async with _client(region) as client:
        result: dict[str, Any] = await client.create_subnet_group(
            SubnetGroupName="my_subnet_group",
            Description="This is my subnet group",
            SubnetIds=[subnet1.id, subnet2.id],
            Tags=[{"Key": "foo", "Value": "bar"}],
        )
    return result


@mock_aws()
@pytest.mark.asyncio
async def test_create_cluster_async() -> None:
    async with _client() as client:
        resp = await client.create_cluster(
            ClusterName="test-memory-db", NodeType="db.t4g.small", ACLName="open-access"
        )
    cluster = resp["Cluster"]
    assert cluster["Name"] == "test-memory-db"
    assert "Status" in cluster
    assert "NumberOfShards" in cluster


@pytest.mark.asyncio
async def test_create_duplicate_cluster_fails_async() -> None:
    with mock_aws():
        async with _client() as client:
            await client.create_cluster(
                ClusterName="foo-bar", NodeType="db.t4g.small", ACLName="open-access"
            )
            with pytest.raises(ClientError) as ex:
                await client.create_cluster(
                    ClusterName="foo-bar",
                    NodeType="db.t4g.small",
                    ACLName="open-access",
                )
    err = ex.value.response["Error"]
    assert err["Code"] == "ClusterAlreadyExistsFault"


@pytest.mark.asyncio
async def test_create_subnet_group_async() -> None:
    with mock_aws():
        subnet_group = await _create_subnet_group(REGION)
    sg = subnet_group["SubnetGroup"]
    assert sg["Name"] == "my_subnet_group"
    assert sg["Description"] == "This is my subnet group"
    assert sg["VpcId"]
    assert sg["Subnets"]
    assert sg["ARN"]


@pytest.mark.asyncio
async def test_create_cluster_with_subnet_group_async() -> None:
    with mock_aws():
        subnet_group = await _create_subnet_group(REGION)
        async with _client() as client:
            resp = await client.create_cluster(
                ClusterName="test-memory-db",
                NodeType="db.t4g.small",
                SubnetGroupName=subnet_group["SubnetGroup"]["Name"],
                ACLName="open-access",
            )
    assert resp["Cluster"]["SubnetGroupName"] == "my_subnet_group"


@pytest.mark.asyncio
async def test_create_duplicate_subnet_group_fails_async() -> None:
    with mock_aws():
        await _create_subnet_group(REGION)
        with pytest.raises(ClientError) as ex:
            await _create_subnet_group(REGION)
    err = ex.value.response["Error"]
    assert err["Code"] == "SubnetGroupAlreadyExistsFault"


@pytest.mark.asyncio
async def test_create_invalid_subnet_group_fails_async() -> None:
    with mock_aws():
        async with _client() as client:
            with pytest.raises(ClientError) as ex:
                await client.create_subnet_group(
                    SubnetGroupName="foo-bar", SubnetIds=["foo", "bar"]
                )
    err = ex.value.response["Error"]
    assert err["Code"] == "InvalidSubnetError"


@pytest.mark.asyncio
async def test_create_snapshot_async() -> None:
    with mock_aws():
        subnet_group = await _create_subnet_group(REGION)
        async with _client() as client:
            cluster = await client.create_cluster(
                ClusterName="test-memory-db",
                Description="Test memorydb cluster",
                NodeType="db.t4g.small",
                SubnetGroupName=subnet_group["SubnetGroup"]["Name"],
                ACLName="open-access",
            )
            resp = await client.create_snapshot(
                ClusterName=cluster["Cluster"]["Name"],
                SnapshotName="my-snapshot-1",
                Tags=[{"Key": "foo", "Value": "bar"}],
            )
    snapshot = resp["Snapshot"]
    assert snapshot["Name"] == "my-snapshot-1"
    assert snapshot["Status"]
    assert snapshot["Source"] == "manual"
    assert "ARN" in snapshot
    assert "ClusterConfiguration" in snapshot
    assert "DataTiering" in snapshot


@pytest.mark.asyncio
async def test_create_snapshot_with_non_existing_cluster_fails_async() -> None:
    with mock_aws():
        async with _client() as client:
            with pytest.raises(ClientError) as ex:
                await client.create_snapshot(
                    ClusterName="foobar", SnapshotName="my-snapshot-1"
                )
    err = ex.value.response["Error"]
    assert err["Code"] == "ClusterNotFoundFault"


@pytest.mark.asyncio
async def test_create_duplicate_snapshot_fails_async() -> None:
    with mock_aws():
        async with _client() as client:
            cluster = await client.create_cluster(
                ClusterName="test-memory-db",
                NodeType="db.t4g.small",
                ACLName="open-access",
            )
            await client.create_snapshot(
                ClusterName=cluster["Cluster"]["Name"], SnapshotName="my-snapshot-1"
            )
            with pytest.raises(ClientError) as ex:
                await client.create_snapshot(
                    ClusterName=cluster["Cluster"]["Name"], SnapshotName="my-snapshot-1"
                )
    err = ex.value.response["Error"]
    assert err["Code"] == "SnapshotAlreadyExistsFault"


@pytest.mark.asyncio
async def test_describe_clusters_async() -> None:
    with mock_aws():
        async with _client() as client:
            for i in range(1, 3):
                await client.create_cluster(
                    ClusterName=f"test-memory-db-{i}",
                    NodeType="db.t4g.small",
                    ACLName="open-access",
                )
            resp = await client.describe_clusters()
    assert len(resp["Clusters"]) == 2
    assert "Shards" not in resp["Clusters"][0]


@pytest.mark.asyncio
async def test_describe_clusters_with_shard_details_async() -> None:
    with mock_aws():
        async with _client() as client:
            for i in range(1, 3):
                await client.create_cluster(
                    ClusterName=f"test-memory-db-{i}",
                    NodeType="db.t4g.small",
                    ACLName="open-access",
                )
            resp = await client.describe_clusters(
                ClusterName="test-memory-db-1", ShowShardDetails=True
            )
    assert resp["Clusters"][0]["Name"] == "test-memory-db-1"
    assert len(resp["Clusters"]) == 1
    assert "Shards" in resp["Clusters"][0]
