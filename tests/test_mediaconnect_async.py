from __future__ import annotations

from typing import Any, TYPE_CHECKING
from uuid import UUID

import aioboto3
from moto.core import DEFAULT_ACCOUNT_ID as ACCOUNT_ID  # type: ignore[attr-defined]
import pytest

from aiomoto import mock_aws


if TYPE_CHECKING:
    from aioboto3.client import ClientCreatorContext


REGION = "eu-west-1"


def _client() -> ClientCreatorContext[Any]:
    return aioboto3.Session().client("mediaconnect", region_name=REGION)


def _source(name: str = "Source-A") -> dict[str, Any]:
    return {
        "Decryption": {"Algorithm": "aes256", "RoleArn": "some:role"},
        "Description": "A source",
        "Name": name,
    }


def _create_flow_config(name: str, **kwargs: Any) -> dict[str, Any]:
    availability_zone = kwargs.get("availability_zone", "AZ1")
    entitlements = kwargs.get(
        "entitlements",
        [
            {
                "DataTransferSubscriberFeePercent": 12,
                "Description": "An entitlement",
                "Encryption": {"Algorithm": "aes256", "RoleArn": "some:role"},
                "EntitlementStatus": "ENABLED",
                "Name": "Entitlement-A",
                "Subscribers": [],
            }
        ],
    )
    outputs = kwargs.get(
        "outputs",
        [
            {"Name": "Output-1", "Protocol": "zixi-push"},
            {"Name": "Output-2", "Protocol": "zixi-pull"},
            {"Name": "Output-3", "Protocol": "srt-listener"},
        ],
    )
    source = kwargs.get("source", _source())
    source_failover_config = kwargs.get("source_failover_config", {})
    sources = kwargs.get("sources", [])
    vpc_interfaces = kwargs.get("vpc_interfaces", [])
    maintenance = kwargs.get("maintenance", {})
    flow_config: dict[str, Any] = {"Name": name}
    optional_flow_config: dict[str, Any] = {
        "AvailabilityZone": availability_zone,
        "Entitlements": entitlements,
        "Outputs": outputs,
        "Source": source,
        "SourceFailoverConfig": source_failover_config,
        "Sources": sources,
        "VpcInterfaces": vpc_interfaces,
        "Maintenance": maintenance,
    }
    flow_config.update({k: v for k, v in optional_flow_config.items() if v})
    return flow_config


def _check_mediaconnect_arn(type_: str, arn: str, name: str) -> None:
    parts = arn.split(":")
    assert parts[:6] == ["arn", "aws", "mediaconnect", REGION, ACCOUNT_ID, type_]
    UUID(parts[6])
    assert parts[-1] == name


@pytest.mark.asyncio
async def test_create_flow_succeeds() -> None:
    with mock_aws():
        async with _client() as client:
            channel_config = _create_flow_config("test-Flow-1")
            response = await client.create_flow(**channel_config)

    assert response["ResponseMetadata"]["HTTPStatusCode"] == 200
    _check_mediaconnect_arn(
        type_="flow", arn=response["Flow"]["FlowArn"], name="test-Flow-1"
    )
    assert response["Flow"]["Name"] == "test-Flow-1"
    assert response["Flow"]["Status"] == "STANDBY"
    assert response["Flow"]["Outputs"][0]["Name"] == "Output-1"
    assert response["Flow"]["Outputs"][1]["ListenerAddress"] == "1.0.0.0"
    assert response["Flow"]["Outputs"][2]["ListenerAddress"] == "2.0.0.0"
    assert response["Flow"]["Source"]["IngestIp"] == "127.0.0.0"
    _check_mediaconnect_arn(
        type_="source", arn=response["Flow"]["Sources"][0]["SourceArn"], name="Source-A"
    )


@pytest.mark.asyncio
async def test_create_flow_with_maintenance_succeeds() -> None:
    with mock_aws():
        async with _client() as client:
            channel_config = _create_flow_config(
                "test-Flow-2",
                maintenance={
                    "MaintenanceDay": "Sunday",
                    "MaintenanceStartHour": "02:00",
                },
            )
            response = await client.create_flow(**channel_config)

    assert response["ResponseMetadata"]["HTTPStatusCode"] == 200
    assert response["Flow"]["Maintenance"]["MaintenanceDay"] == "Sunday"
    assert response["Flow"]["Maintenance"]["MaintenanceStartHour"] == "02:00"


@pytest.mark.asyncio
async def test_create_flow_alternative_succeeds() -> None:
    with mock_aws():
        async with _client() as client:
            channel_config = _create_flow_config(
                "test-Flow-1",
                source=None,
                sources=[_source(), _source("Source-B")],
                source_failover_config={
                    "FailoverMode": "FAILOVER",
                    "SourcePriority": {"PrimarySource": "Source-B"},
                    "State": "ENABLED",
                },
                outputs=None,
            )

            response = await client.create_flow(**channel_config)

    assert response["ResponseMetadata"]["HTTPStatusCode"] == 200
    _check_mediaconnect_arn(
        type_="flow", arn=response["Flow"]["FlowArn"], name="test-Flow-1"
    )
    assert response["Flow"]["Name"] == "test-Flow-1"
    assert response["Flow"]["Status"] == "STANDBY"
    assert response["Flow"]["Sources"][0]["IngestIp"] == "127.0.0.0"
    assert response["Flow"]["Sources"][1]["IngestIp"] == "127.0.0.1"
    _check_mediaconnect_arn(
        type_="source", arn=response["Flow"]["Sources"][0]["SourceArn"], name="Source-A"
    )


@pytest.mark.asyncio
async def test_list_flows_succeeds() -> None:
    with mock_aws():
        async with _client() as client:
            flow_1_config = _create_flow_config("test-Flow-1")
            flow_2_config = _create_flow_config("test-Flow-2")

            await client.create_flow(**flow_1_config)
            await client.create_flow(**flow_2_config)

            response = await client.list_flows()

    assert len(response["Flows"]) == 2
    assert response["Flows"][0]["Name"] == "test-Flow-1"
    assert response["Flows"][0]["AvailabilityZone"] == "AZ1"
    assert response["Flows"][0]["SourceType"] == "OWNED"
    assert response["Flows"][0]["Status"] == "STANDBY"


@pytest.mark.asyncio
async def test_describe_flow_succeeds() -> None:
    with mock_aws():
        async with _client() as client:
            channel_config = _create_flow_config("test-Flow-1")

            create_response = await client.create_flow(**channel_config)
            flow_arn = create_response["Flow"]["FlowArn"]
            describe_response = await client.describe_flow(FlowArn=flow_arn)

    assert describe_response["ResponseMetadata"]["HTTPStatusCode"] == 200
    assert describe_response["Flow"]["Name"] == "test-Flow-1"


@pytest.mark.asyncio
async def test_delete_flow_succeeds() -> None:
    with mock_aws():
        async with _client() as client:
            channel_config = _create_flow_config("test-Flow-1")
            create_response = await client.create_flow(**channel_config)
            flow_arn = create_response["Flow"]["FlowArn"]
            delete_response = await client.delete_flow(FlowArn=flow_arn)

    assert delete_response["ResponseMetadata"]["HTTPStatusCode"] == 200
    assert delete_response["FlowArn"] == flow_arn
    assert delete_response["Status"] == "STANDBY"


@pytest.mark.asyncio
async def test_start_stop_flow_succeeds() -> None:
    with mock_aws():
        async with _client() as client:
            channel_config = _create_flow_config("test-Flow-1")
            flow_arn = (await client.create_flow(**channel_config))["Flow"]["FlowArn"]

            await client.start_flow(FlowArn=flow_arn)
            await client.stop_flow(FlowArn=flow_arn)
            flow = await client.describe_flow(FlowArn=flow_arn)

    assert flow["Flow"]["Status"] == "STANDBY"
