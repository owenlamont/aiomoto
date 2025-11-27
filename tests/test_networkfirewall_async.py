from typing import Any, TYPE_CHECKING

import aioboto3
import pytest

from aiomoto import mock_aws


if TYPE_CHECKING:
    from aioboto3.client import ClientCreatorContext


REGION = "us-east-1"


def _client(region: str = REGION) -> "ClientCreatorContext[Any]":
    return aioboto3.Session().client("network-firewall", region_name=region)


@mock_aws()
@pytest.mark.asyncio
async def test_create_firewall_async() -> None:
    async with _client() as client:
        firewall = (
            await client.create_firewall(
                FirewallName="test-firewall",
                FirewallPolicyArn=(
                    "arn:aws:network-firewall:ap-southeast-1:123456789012:"
                    "firewall-policy/test-policy"
                ),
                DeleteProtection=False,
                SubnetChangeProtection=False,
            )
        )["Firewall"]

    assert firewall["FirewallName"] == "test-firewall"
    assert "FirewallArn" in firewall
    assert firewall["DeleteProtection"] is False
    assert firewall["SubnetChangeProtection"] is False
    assert firewall["FirewallPolicyChangeProtection"] is True


@pytest.mark.asyncio
async def test_describe_logging_configuration_async() -> None:
    with mock_aws():
        async with _client("eu-west-1") as client:
            firewall = (
                await client.create_firewall(
                    FirewallName="test-firewall",
                    FirewallPolicyArn=(
                        "arn:aws:network-firewall:ap-southeast-1:123456789012:"
                        "firewall-policy/test-policy"
                    ),
                )
            )["Firewall"]

            logging_config = {
                "LogDestinationConfigs": [
                    {
                        "LogDestinationType": "S3",
                        "LogDestination": {
                            "bucketName": "DOC-EXAMPLE-BUCKET",
                            "prefix": "alerts",
                        },
                        "LogType": "FLOW",
                    },
                    {
                        "LogDestinationType": "CloudWatchLogs",
                        "LogDestination": {"logGroup": "alert-log-group"},
                        "LogType": "ALERT",
                    },
                ]
            }

            await client.update_logging_configuration(
                FirewallArn=firewall["FirewallArn"], LoggingConfiguration=logging_config
            )

            resp = await client.describe_logging_configuration(
                FirewallArn=firewall["FirewallArn"]
            )

    assert resp["FirewallArn"] == firewall["FirewallArn"]
    log_dest_configs = resp["LoggingConfiguration"]["LogDestinationConfigs"]
    assert len(log_dest_configs) == 2
    assert log_dest_configs[0]["LogDestinationType"] == "S3"
    assert log_dest_configs[0]["LogType"] == "FLOW"
    assert log_dest_configs[1]["LogDestinationType"] == "CloudWatchLogs"
    assert log_dest_configs[1]["LogType"] == "ALERT"


@pytest.mark.asyncio
async def test_describe_logging_configuration_no_config_set_async() -> None:
    with mock_aws():
        async with _client("eu-west-1") as client:
            firewall = (
                await client.create_firewall(
                    FirewallName="test-firewall",
                    FirewallPolicyArn=(
                        "arn:aws:network-firewall:ap-southeast-1:123456789012:"
                        "firewall-policy/test-policy"
                    ),
                )
            )["Firewall"]

            resp = await client.describe_logging_configuration(
                FirewallArn=firewall["FirewallArn"]
            )

    assert resp["FirewallArn"] == firewall["FirewallArn"]
    assert resp["LoggingConfiguration"] == {}


@pytest.mark.asyncio
async def test_update_logging_configuration_async() -> None:
    with mock_aws():
        async with _client("ap-southeast-1") as client:
            firewall = (
                await client.create_firewall(
                    FirewallName="test-firewall",
                    FirewallPolicyArn=(
                        "arn:aws:network-firewall:ap-southeast-1:123456789012:"
                        "firewall-policy/test-policy"
                    ),
                )
            )["Firewall"]

            logging_config = {
                "LogDestinationConfigs": [
                    {
                        "LogDestinationType": "S3",
                        "LogDestination": {
                            "bucketName": "DOC-EXAMPLE-BUCKET",
                            "prefix": "alerts",
                        },
                        "LogType": "FLOW",
                    }
                ]
            }

            resp = await client.update_logging_configuration(
                FirewallArn=firewall["FirewallArn"], LoggingConfiguration=logging_config
            )

    assert resp["FirewallArn"] == firewall["FirewallArn"]
    assert resp["FirewallName"] == "test-firewall"
    assert len(resp["LoggingConfiguration"]["LogDestinationConfigs"]) == 1
    assert resp["LoggingConfiguration"] == logging_config


@pytest.mark.asyncio
async def test_list_firewalls_async() -> None:
    with mock_aws():
        async with _client("ap-southeast-1") as client:
            for i in range(5):
                await client.create_firewall(
                    FirewallName=f"test-firewall-{i}",
                    FirewallPolicyArn=(
                        "arn:aws:network-firewall:ap-southeast-1:"
                        "123456789012:firewall-policy/test-policy"
                    ),
                    VpcId=f"vpc-1234567{i}",
                )

            resp_all = await client.list_firewalls()
            resp_vpc = await client.list_firewalls(VpcIds=["vpc-12345671"])

    assert len(resp_all["Firewalls"]) == 5
    assert resp_all["Firewalls"][0]["FirewallName"] == "test-firewall-0"
    assert "FirewallArn" in resp_all["Firewalls"][0]
    assert len(resp_vpc["Firewalls"]) == 1
    assert resp_vpc["Firewalls"][0]["FirewallName"] == "test-firewall-1"


@pytest.mark.asyncio
async def test_describe_firewall_async() -> None:
    with mock_aws():
        async with _client("ap-southeast-1") as client:
            firewall = (
                await client.create_firewall(
                    FirewallName="test-firewall",
                    FirewallPolicyArn=(
                        "arn:aws:network-firewall:ap-southeast-1:123456789012:"
                        "firewall-policy/test-policy"
                    ),
                    VpcId="vpc-12345678",
                    SubnetMappings=[{"SubnetId": "subnet-12345678"}],
                    DeleteProtection=False,
                    SubnetChangeProtection=False,
                    FirewallPolicyChangeProtection=False,
                    Description="Test firewall",
                    Tags=[{"Key": "Name", "Value": "test-firewall"}],
                )
            )["Firewall"]

            resp_arn = await client.describe_firewall(
                FirewallArn=firewall["FirewallArn"]
            )
            resp_name = await client.describe_firewall(FirewallName="test-firewall")

    assert resp_arn["Firewall"]["FirewallName"] == "test-firewall"
    assert resp_arn["Firewall"]["VpcId"] == "vpc-12345678"
    assert resp_arn["Firewall"]["SubnetMappings"] == [{"SubnetId": "subnet-12345678"}]
    assert resp_arn["Firewall"]["DeleteProtection"] is False
    assert resp_arn["Firewall"]["SubnetChangeProtection"] is False
    assert resp_arn["Firewall"]["FirewallPolicyChangeProtection"] is False
    assert resp_arn["Firewall"]["Description"] == "Test firewall"
    assert resp_arn["Firewall"]["Tags"] == [{"Key": "Name", "Value": "test-firewall"}]
    assert resp_arn["UpdateToken"]

    assert resp_name["Firewall"]["FirewallName"] == "test-firewall"
