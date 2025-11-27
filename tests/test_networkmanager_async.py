from __future__ import annotations

from typing import Any, TYPE_CHECKING

import aioboto3
from moto.core import DEFAULT_ACCOUNT_ID as ACCOUNT_ID  # type: ignore[attr-defined]
import pytest

from aiomoto import mock_aws


if TYPE_CHECKING:
    from aioboto3.client import ClientCreatorContext

REGION = "us-east-1"


def _client() -> ClientCreatorContext[Any]:
    return aioboto3.Session().client("networkmanager", region_name=REGION)


async def _create_global_network(client: Any) -> str:
    resp = await client.create_global_network(Description="Test global network")
    return str(resp["GlobalNetwork"]["GlobalNetworkId"])


@pytest.mark.asyncio
async def test_create_global_network_async() -> None:
    with mock_aws():
        async with _client() as client:
            resp = await client.create_global_network(
                Description="Test global network",
                Tags=[{"Key": "Name", "Value": "TestNetwork"}],
            )

            global_network = resp["GlobalNetwork"]
            arn = (
                f"arn:aws:networkmanager:{ACCOUNT_ID}:global-network/"
                f"{global_network['GlobalNetworkId']}"
            )
            desc = (await client.describe_global_networks())["GlobalNetworks"][0]

    assert global_network["GlobalNetworkArn"] == arn
    assert global_network["Description"] == "Test global network"
    assert global_network["Tags"] == [{"Key": "Name", "Value": "TestNetwork"}]
    assert global_network["State"] == "PENDING"
    assert desc["GlobalNetworkId"] == global_network["GlobalNetworkId"]
    assert desc["State"] == "AVAILABLE"


@pytest.mark.asyncio
async def test_create_core_network_async() -> None:
    with mock_aws():
        async with _client() as client:
            gn_id = await _create_global_network(client)
            resp = await client.create_core_network(
                GlobalNetworkId=gn_id,
                Description="Test core network",
                Tags=[{"Key": "Name", "Value": "TestNetwork"}],
                PolicyDocument="policy-document",
                ClientToken="client-token",
            )

    core_network = resp["CoreNetwork"]
    assert core_network["CoreNetworkArn"] == (
        f"arn:aws:networkmanager:{ACCOUNT_ID}:core-network/"
        f"{core_network['CoreNetworkId']}"
    )
    assert core_network["GlobalNetworkId"] == gn_id
    assert core_network["Description"] == "Test core network"
    assert len(core_network["Tags"]) == 1


@pytest.mark.asyncio
async def test_delete_core_network_async() -> None:
    with mock_aws():
        async with _client() as client:
            gn_id = await _create_global_network(client)
            cn_id = (await client.create_core_network(GlobalNetworkId=gn_id))[
                "CoreNetwork"
            ]["CoreNetworkId"]
            assert len((await client.list_core_networks())["CoreNetworks"]) == 1
            resp = await client.delete_core_network(CoreNetworkId=cn_id)
            remaining = (await client.list_core_networks())["CoreNetworks"]

    assert resp["CoreNetwork"]["CoreNetworkId"] == cn_id
    assert resp["CoreNetwork"]["State"] == "DELETING"
    assert len(remaining) == 0


@pytest.mark.asyncio
async def test_tag_resource_async() -> None:
    test_tags = [
        {"Key": "Moto", "Value": "TestTag"},
        {"Key": "Owner", "Value": "Alice"},
    ]
    with mock_aws():
        async with _client() as client:
            gn_id = await _create_global_network(client)
            cn = (await client.create_core_network(GlobalNetworkId=gn_id))[
                "CoreNetwork"
            ]

            await client.tag_resource(ResourceArn=cn["CoreNetworkArn"], Tags=test_tags)
            updated_cn = (
                await client.get_core_network(CoreNetworkId=cn["CoreNetworkId"])
            )["CoreNetwork"]

            gn_arn = (await client.describe_global_networks())["GlobalNetworks"][0][
                "GlobalNetworkArn"
            ]
            await client.tag_resource(ResourceArn=gn_arn, Tags=test_tags)
            updated_gn = (
                await client.describe_global_networks(GlobalNetworkIds=[gn_id])
            )["GlobalNetworks"][0]

            site = (
                await client.create_site(
                    GlobalNetworkId=gn_id,
                    Description="Test site",
                    Location={
                        "Address": "123 Main St",
                        "Latitude": "47.6062",
                        "Longitude": "122.3321",
                    },
                )
            )["Site"]
            await client.tag_resource(ResourceArn=site["SiteArn"], Tags=test_tags)
            updated_site = (
                await client.get_sites(GlobalNetworkId=gn_id, SiteIds=[site["SiteId"]])
            )["Sites"][0]

    assert updated_cn["Tags"] == test_tags
    assert updated_gn["Tags"] == test_tags
    assert updated_site["Tags"] == test_tags


@pytest.mark.asyncio
async def test_untag_resource_async() -> None:
    with mock_aws():
        async with _client() as client:
            gn_id = await _create_global_network(client)
            cn = (
                await client.create_core_network(
                    GlobalNetworkId=gn_id,
                    Tags=[
                        {"Key": "Name", "Value": "TestNetwork"},
                        {"Key": "DeleteMe", "Value": "DeleteThisTag!"},
                    ],
                )
            )["CoreNetwork"]

            await client.untag_resource(
                ResourceArn=cn["CoreNetworkArn"], TagKeys=["DeleteMe"]
            )
            updated_cn = (
                await client.get_core_network(CoreNetworkId=cn["CoreNetworkId"])
            )["CoreNetwork"]

    assert updated_cn["Tags"] == [{"Key": "Name", "Value": "TestNetwork"}]


@pytest.mark.asyncio
async def test_list_core_networks_async() -> None:
    num_networks = 3
    with mock_aws():
        async with _client() as client:
            for _ in range(num_networks):
                gn_id = await _create_global_network(client)
                await client.create_core_network(GlobalNetworkId=gn_id)

            resp = await client.list_core_networks()

    assert len(resp["CoreNetworks"]) == num_networks
    network = resp["CoreNetworks"][0]
    expected_fields = [
        "CoreNetworkId",
        "CoreNetworkArn",
        "GlobalNetworkId",
        "State",
        "Tags",
        "OwnerAccountId",
    ]
    for field in expected_fields:
        assert field in network
    assert network["OwnerAccountId"] == ACCOUNT_ID


@pytest.mark.asyncio
async def test_get_core_network_async() -> None:
    with mock_aws():
        async with _client() as client:
            gn_id = await _create_global_network(client)
            cn_id = (
                await client.create_core_network(
                    GlobalNetworkId=gn_id,
                    Description="Test core network",
                    Tags=[{"Key": "Name", "Value": "TestNetwork"}],
                    PolicyDocument="policy-document",
                    ClientToken="client-token",
                )
            )["CoreNetwork"]["CoreNetworkId"]

            resp = await client.get_core_network(CoreNetworkId=cn_id)

    assert resp["CoreNetwork"]["CoreNetworkId"] == cn_id
    assert resp["CoreNetwork"]["Description"] == "Test core network"
    assert len(resp["CoreNetwork"]["Tags"]) == 1
