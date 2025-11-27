from __future__ import annotations

from datetime import datetime
from typing import Any, TYPE_CHECKING

import aioboto3
from dateutil.tz import tzutc  # type: ignore[import-untyped]
from freezegun import freeze_time
import pytest

from aiomoto import mock_aws


if TYPE_CHECKING:
    from aioboto3.client import ClientCreatorContext


REGION = "eu-west-1"


def _client() -> ClientCreatorContext[Any]:
    return aioboto3.Session().client("panorama", region_name=REGION)


@pytest.mark.asyncio
async def test_provision_device_async() -> None:
    with mock_aws():
        async with _client() as client:
            resp = await client.provision_device(
                Description="test-device-name",
                Name="test-device-name",
                NetworkingConfiguration={
                    "Ethernet0": {
                        "ConnectionType": "STATIC_IP",
                        "StaticIpConnectionInfo": {
                            "DefaultGateway": "192.168.1.1",
                            "Dns": ["8.8.8.8"],
                            "IpAddress": "192.168.1.10",
                            "Mask": "255.255.255.0",
                        },
                    },
                    "Ethernet1": {"ConnectionType": "dhcp"},
                    "Ntp": {"NtpServers": ["0.pool.ntp.org", "1.pool.ntp.org"]},
                },
                Tags={"Key": "test-key", "Value": "test-value"},
            )

    assert (
        resp["Arn"] == "arn:aws:panorama:eu-west-1:123456789012:device/test-device-name"
    )
    assert resp["Certificates"] == b"certificate"
    assert resp["DeviceId"]
    assert resp["Status"] == "SUCCEEDED"


@pytest.mark.asyncio
async def test_describe_device_async() -> None:
    with mock_aws():
        async with _client() as client:
            with freeze_time("2020-01-01 12:00:00", real_asyncio=True):
                resp = await client.provision_device(
                    Description="test device description",
                    Name="test-device-name",
                    NetworkingConfiguration={
                        "Ethernet0": {
                            "ConnectionType": "STATIC_IP",
                            "StaticIpConnectionInfo": {
                                "DefaultGateway": "192.168.1.1",
                                "Dns": ["8.8.8.8"],
                                "IpAddress": "192.168.1.10",
                                "Mask": "255.255.255.0",
                            },
                        },
                        "Ethernet1": {"ConnectionType": "dhcp"},
                        "Ntp": {"NtpServers": ["0.pool.ntp.org", "1.pool.ntp.org"]},
                    },
                    Tags={"Key": "test-key", "Value": "test-value"},
                )

            desc = await client.describe_device(DeviceId=resp["DeviceId"])

    assert (
        desc["Arn"] == "arn:aws:panorama:eu-west-1:123456789012:device/test-device-name"
    )
    assert desc["CreatedTime"] == datetime(2020, 1, 1, 12, 0, tzinfo=tzutc())
    assert desc["DeviceAggregatedStatus"] == "ONLINE"
    assert desc["ProvisioningStatus"] == "SUCCEEDED"
    assert desc["Tags"] == {"Key": "test-key", "Value": "test-value"}
