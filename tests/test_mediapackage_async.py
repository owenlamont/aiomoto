from __future__ import annotations

from typing import Any, TYPE_CHECKING

import aioboto3
from botocore.exceptions import ClientError
import pytest

from aiomoto import mock_aws


if TYPE_CHECKING:
    from aioboto3.client import ClientCreatorContext


REGION = "eu-west-1"


def _client() -> ClientCreatorContext[Any]:
    return aioboto3.Session().client("mediapackage", region_name=REGION)


def _create_channel_config(**kwargs: object) -> dict:
    channel_id = kwargs.get("id", "channel-id")
    description = kwargs.get("description", "Awesome channel!")
    tags = kwargs.get("tags", {"Customer": "moto"})
    return {"Description": description, "Id": channel_id, "Tags": tags}


def _create_origin_endpoint_config(**kwargs: object) -> dict:
    authorization = kwargs.get(
        "authorization",
        {"CdnIdentifierSecret": "cdn-id-secret", "SecretsRoleArn": "secrets-arn"},
    )
    channel_id = kwargs.get("channel_id", "channel-id")
    cmaf_package = kwargs.get("cmafpackage", {"HlsManifests": []})
    dash_package = kwargs.get("dash_package", {"AdTriggers": []})
    description = kwargs.get("description", "channel-description")
    hls_package = kwargs.get("hls_package", {"AdMarkers": "NONE"})
    endpoint_id = kwargs.get("id", "origin-endpoint-id")
    manifest_name = kwargs.get("manifest_name", "manifest-name")
    mss_package = kwargs.get("mss_package", {"ManifestWindowSeconds": 1})
    origination = kwargs.get("origination", "ALLOW")
    startover_window_seconds = kwargs.get("startover_window_seconds", 1)
    tags = kwargs.get("tags", {"Customer": "moto"})
    time_delay_seconds = kwargs.get("time_delay_seconds", 1)
    whitelist = kwargs.get("whitelist", ["whitelist"])
    return {
        "Authorization": authorization,
        "ChannelId": channel_id,
        "CmafPackage": cmaf_package,
        "DashPackage": dash_package,
        "Description": description,
        "HlsPackage": hls_package,
        "Id": endpoint_id,
        "ManifestName": manifest_name,
        "MssPackage": mss_package,
        "Origination": origination,
        "StartoverWindowSeconds": startover_window_seconds,
        "Tags": tags,
        "TimeDelaySeconds": time_delay_seconds,
        "Whitelist": whitelist,
    }


@pytest.mark.asyncio
async def test_create_channel_succeeds() -> None:
    with mock_aws():
        async with _client() as client:
            channel_config = _create_channel_config()
            channel = await client.create_channel(**channel_config)

    assert channel["ResponseMetadata"]["HTTPStatusCode"] == 200
    assert channel["Arn"] == f"arn:aws:mediapackage:channel:{channel['Id']}"
    assert channel["Description"] == "Awesome channel!"
    assert channel["Id"] == "channel-id"
    assert channel["Tags"]["Customer"] == "moto"


@pytest.mark.asyncio
async def test_describe_channel_succeeds() -> None:
    with mock_aws():
        async with _client() as client:
            channel_config = _create_channel_config()
            channel_id = (await client.create_channel(**channel_config))["Id"]
            channel = await client.describe_channel(Id=channel_id)

    assert channel["Arn"] == f"arn:aws:mediapackage:channel:{channel['Id']}"
    assert channel["Description"] == channel_config["Description"]
    assert channel["Tags"]["Customer"] == "moto"


@pytest.mark.asyncio
async def test_describe_unknown_channel_error() -> None:
    with mock_aws():
        async with _client() as client:
            channel_id = "unknown-channel"
            with pytest.raises(ClientError):  # pragma: no branch
                await client.describe_channel(Id=channel_id)


@pytest.mark.asyncio
async def test_delete_unknown_channel_error() -> None:
    with mock_aws():
        async with _client() as client:
            channel_id = "unknown-channel"
            with pytest.raises(ClientError):  # pragma: no branch
                await client.delete_channel(Id=channel_id)


@pytest.mark.asyncio
async def test_delete_channel() -> None:
    with mock_aws():
        async with _client() as client:
            channel_config = _create_channel_config()
            create_response = await client.create_channel(**channel_config)
            channels_list = (await client.list_channels())["Channels"]
            await client.delete_channel(Id=create_response["Id"])
            post_deletion_channels_list = (await client.list_channels())["Channels"]

    assert len(post_deletion_channels_list) == len(channels_list) - 1


@pytest.mark.asyncio
async def test_list_channels() -> None:
    with mock_aws():
        async with _client() as client:
            channel_config = _create_channel_config()
            await client.create_channel(**channel_config)
            channels_list = (await client.list_channels())["Channels"]

    assert len(channels_list) == 1
    channel = channels_list[0]
    assert channel["Arn"] == f"arn:aws:mediapackage:channel:{channel['Id']}"
    assert channel["Description"] == channel_config["Description"]
    assert channel["Tags"]["Customer"] == "moto"


@pytest.mark.asyncio
async def test_create_origin_endpoint_succeeds() -> None:
    with mock_aws():
        async with _client() as client:
            origin_endpoint_config = _create_origin_endpoint_config()

            endpoint = await client.create_origin_endpoint(**origin_endpoint_config)

    assert endpoint["ResponseMetadata"]["HTTPStatusCode"] == 200
    assert endpoint["Arn"] == f"arn:aws:mediapackage:origin_endpoint:{endpoint['Id']}"
    assert endpoint["ChannelId"] == origin_endpoint_config["ChannelId"]
    assert endpoint["Description"] == origin_endpoint_config["Description"]
    assert endpoint["HlsPackage"] == origin_endpoint_config["HlsPackage"]
    assert endpoint["Origination"] == "ALLOW"
    assert endpoint["Whitelist"] == ["whitelist"]
    assert endpoint["TimeDelaySeconds"] == 1


@pytest.mark.asyncio
async def test_describe_origin_endpoint_succeeds() -> None:
    with mock_aws():
        async with _client() as client:
            origin_endpoint_config = _create_origin_endpoint_config()
            endpoint_id = (
                await client.create_origin_endpoint(**origin_endpoint_config)
            )["Id"]
            endpoint = await client.describe_origin_endpoint(Id=endpoint_id)

    assert endpoint["ResponseMetadata"]["HTTPStatusCode"] == 200
    assert endpoint["Arn"] == f"arn:aws:mediapackage:origin_endpoint:{endpoint['Id']}"
    assert endpoint["ChannelId"] == origin_endpoint_config["ChannelId"]
    assert endpoint["Description"] == origin_endpoint_config["Description"]
    assert endpoint["HlsPackage"] == origin_endpoint_config["HlsPackage"]
    assert endpoint["Origination"] == "ALLOW"
    assert (
        endpoint["Url"]
        == f"https://origin-endpoint.mediapackage.{REGION}.amazonaws.com/{endpoint['Id']}"
    )


@pytest.mark.asyncio
async def test_describe_unknown_origin_endpoint_error() -> None:
    with mock_aws():
        async with _client() as client:
            channel_id = "unknown-channel"
            with pytest.raises(ClientError):  # pragma: no branch
                await client.describe_origin_endpoint(Id=channel_id)


@pytest.mark.asyncio
async def test_delete_origin_endpoint() -> None:
    with mock_aws():
        async with _client() as client:
            origin_endpoint_config = _create_origin_endpoint_config()
            create_response = await client.create_origin_endpoint(
                **origin_endpoint_config
            )
            origin_endpoints_list = (await client.list_origin_endpoints())[
                "OriginEndpoints"
            ]
            await client.delete_origin_endpoint(Id=create_response["Id"])
            post_deletion_origin_endpoints_list = (
                await client.list_origin_endpoints()
            )["OriginEndpoints"]

    assert len(post_deletion_origin_endpoints_list) == len(origin_endpoints_list) - 1


@pytest.mark.asyncio
async def test_delete_unknown_origin_endpoint_error() -> None:
    with mock_aws():
        async with _client() as client:
            channel_id = "unknown-channel"
            with pytest.raises(ClientError):  # pragma: no branch
                await client.delete_origin_endpoint(Id=channel_id)


@pytest.mark.asyncio
async def test_update_origin_endpoint_succeeds() -> None:
    with mock_aws():
        async with _client() as client:
            origin_endpoint_config = _create_origin_endpoint_config()
            endpoint_id = (
                await client.create_origin_endpoint(**origin_endpoint_config)
            )["Id"]

            endpoint = await client.update_origin_endpoint(
                Id=endpoint_id,
                Description="updated-channel-description",
                ManifestName="updated-manifest-name",
                Whitelist=["new-whitelist-item"],
            )

    assert endpoint["Description"] == "updated-channel-description"
    assert endpoint["ManifestName"] == "updated-manifest-name"
    assert endpoint["Whitelist"] == ["new-whitelist-item"]


@pytest.mark.asyncio
async def test_update_unknown_origin_endpoint_error() -> None:
    with mock_aws():
        async with _client() as client:
            channel_id = "unknown-channel"
            with pytest.raises(ClientError):  # pragma: no branch
                await client.update_origin_endpoint(
                    Id=channel_id,
                    Description="updated-channel-description",
                    ManifestName="updated-manifest-name",
                )


@pytest.mark.asyncio
async def test_list_origin_endpoint_succeeds() -> None:
    with mock_aws():
        async with _client() as client:
            origin_endpoint_config = _create_origin_endpoint_config()
            await client.create_origin_endpoint(**origin_endpoint_config)
            origin_endpoints_list = (await client.list_origin_endpoints())[
                "OriginEndpoints"
            ]

    assert len(origin_endpoints_list) == 1
    endpoint = origin_endpoints_list[0]
    assert endpoint["Arn"] == f"arn:aws:mediapackage:origin_endpoint:{endpoint['Id']}"
    assert endpoint["ChannelId"] == origin_endpoint_config["ChannelId"]
    assert endpoint["Description"] == origin_endpoint_config["Description"]
    assert endpoint["HlsPackage"] == origin_endpoint_config["HlsPackage"]
    assert endpoint["Origination"] == "ALLOW"
