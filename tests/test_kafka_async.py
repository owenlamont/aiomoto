from __future__ import annotations

from typing import Any, TYPE_CHECKING

import aioboto3
import pytest

from aiomoto import mock_aws


if TYPE_CHECKING:
    from aioboto3.client import ClientCreatorContext


FAKE_TAGS = {"TestKey": "TestValue", "TestKey2": "TestValue2"}


def _client(region: str) -> ClientCreatorContext[Any]:
    return aioboto3.Session().client("kafka", region_name=region)


@mock_aws()
@pytest.mark.asyncio
async def test_create_cluster_v2_async() -> None:
    async with _client("ap-southeast-1") as client:
        s_cluster_name = "TestServerlessCluster"
        p_cluster_name = "TestProvisionedCluster"

        s_response = await client.create_cluster_v2(
            ClusterName=s_cluster_name,
            Serverless={
                "VpcConfigs": [
                    {
                        "SubnetIds": ["subnet-0123456789abcdef0"],
                        "SecurityGroupIds": ["sg-0123456789abcdef0"],
                    }
                ]
            },
            Tags=FAKE_TAGS,
        )

        p_response = await client.create_cluster_v2(
            ClusterName=p_cluster_name,
            Provisioned={
                "BrokerNodeGroupInfo": {
                    "InstanceType": "kafka.m5.large",
                    "ClientSubnets": ["subnet-0123456789abcdef0"],
                    "SecurityGroups": ["sg-0123456789abcdef0"],
                },
                "KafkaVersion": "2.8.1",
                "NumberOfBrokerNodes": 3,
            },
            Tags=FAKE_TAGS,
        )

        clusters = await client.list_clusters_v2()
        s_resp = await client.describe_cluster_v2(ClusterArn=s_response["ClusterArn"])
        p_resp = await client.describe_cluster_v2(ClusterArn=p_response["ClusterArn"])

    assert s_response["ClusterArn"].startswith("arn:aws:kafka")
    assert s_response["ClusterName"] == s_cluster_name
    assert s_response["State"] == "CREATING"

    assert p_response["ClusterArn"].startswith("arn:aws:kafka")
    assert p_response["ClusterName"] == p_cluster_name
    assert p_response["State"] == "CREATING"

    assert len(clusters["ClusterInfoList"]) == 2
    assert clusters["ClusterInfoList"][0]["ClusterName"] == s_cluster_name
    assert clusters["ClusterInfoList"][0]["ClusterType"] == "SERVERLESS"
    assert clusters["ClusterInfoList"][1]["ClusterName"] == p_cluster_name
    assert clusters["ClusterInfoList"][1]["ClusterType"] == "PROVISIONED"

    s_cluster_info = s_resp["ClusterInfo"]
    p_cluster_info = p_resp["ClusterInfo"]
    assert s_cluster_info["ClusterName"] == s_cluster_name
    assert s_cluster_info["ClusterType"] == "SERVERLESS"
    assert s_cluster_info["Serverless"]["VpcConfigs"][0]["SubnetIds"] == [
        "subnet-0123456789abcdef0"
    ]
    assert s_cluster_info["Serverless"]["VpcConfigs"][0]["SecurityGroupIds"] == [
        "sg-0123456789abcdef0"
    ]
    assert s_cluster_info["Tags"] == FAKE_TAGS

    assert p_cluster_info["ClusterName"] == p_cluster_name
    assert p_cluster_info["ClusterType"] == "PROVISIONED"
    assert (
        p_cluster_info["Provisioned"]["BrokerNodeGroupInfo"]["InstanceType"]
        == "kafka.m5.large"
    )


@pytest.mark.asyncio
async def test_list_tags_for_resource_async() -> None:
    with mock_aws():
        async with _client("us-east-2") as client:
            create_resp = await client.create_cluster(
                ClusterName="TestCluster",
                BrokerNodeGroupInfo={
                    "InstanceType": "kafka.m5.large",
                    "ClientSubnets": ["subnet-0123456789abcdef0"],
                    "SecurityGroups": ["sg-0123456789abcdef0"],
                },
                KafkaVersion="2.8.1",
                NumberOfBrokerNodes=3,
                Tags=FAKE_TAGS,
            )

            temp_tags = {"TestKey3": "TestValue3"}
            await client.tag_resource(
                ResourceArn=create_resp["ClusterArn"], Tags=temp_tags
            )

            tags = await client.list_tags_for_resource(
                ResourceArn=create_resp["ClusterArn"]
            )
            assert tags["Tags"] == {**FAKE_TAGS, **temp_tags}

            await client.untag_resource(
                ResourceArn=create_resp["ClusterArn"], TagKeys=["TestKey3"]
            )

            tags = await client.list_tags_for_resource(
                ResourceArn=create_resp["ClusterArn"]
            )

    assert tags["Tags"] == FAKE_TAGS


@pytest.mark.asyncio
async def test_create_and_delete_cluster_async() -> None:
    with mock_aws():
        async with _client("eu-west-1") as client:
            cluster_name = "TestCluster"
            response = await client.create_cluster(
                ClusterName=cluster_name,
                BrokerNodeGroupInfo={
                    "InstanceType": "kafka.m5.large",
                    "ClientSubnets": ["subnet-0123456789abcdef0"],
                    "SecurityGroups": ["sg-0123456789abcdef0"],
                },
                KafkaVersion="2.8.1",
                NumberOfBrokerNodes=3,
                Tags=FAKE_TAGS,
            )

            clusters = await client.list_clusters()
            resp = await client.describe_cluster(ClusterArn=response["ClusterArn"])

            await client.delete_cluster(ClusterArn=response["ClusterArn"])
            clusters_after = await client.list_clusters()

    assert response["ClusterArn"].startswith("arn:aws:kafka")
    assert response["ClusterName"] == cluster_name
    assert response["State"] == "CREATING"
    assert len(clusters["ClusterInfoList"]) == 1
    assert resp["ClusterInfo"]["ClusterName"] == cluster_name
    assert resp["ClusterInfo"]["CurrentBrokerSoftwareInfo"]["KafkaVersion"] == "2.8.1"
    assert clusters_after["ClusterInfoList"] == []
