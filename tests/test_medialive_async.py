from __future__ import annotations

from typing import Any, TYPE_CHECKING

import aioboto3
from moto.core import DEFAULT_ACCOUNT_ID as ACCOUNT_ID  # type: ignore[attr-defined]
import pytest

from aiomoto import mock_aws


if TYPE_CHECKING:
    from aioboto3.client import ClientCreatorContext


REGION = "eu-west-1"


def _client() -> ClientCreatorContext[Any]:
    return aioboto3.Session().client("medialive", region_name=REGION)


def _create_channel_config(name: str, **kwargs: object) -> dict:
    role_arn = kwargs.get(
        "role_arn", f"arn:aws:iam::{ACCOUNT_ID}:role/TestMediaLiveChannelCreateRole"
    )
    input_id = kwargs.get("input_id", "an-attachment-id")
    input_settings = kwargs.get(
        "input_settings",
        [
            {
                "InputId": input_id,
                "InputSettings": {
                    "DenoiseFilter": "DISABLED",
                    "AudioSelectors": [
                        {"Name": "EnglishLanguage", "SelectorSettings": {}}
                    ],
                    "InputFilter": "AUTO",
                    "DeblockFilter": "DISABLED",
                    "NetworkInputSettings": {
                        "ServerValidation": "CHECK_CRYPTOGRAPHY_AND_VALIDATE_NAME"
                    },
                    "SourceEndBehavior": "CONTINUE",
                    "FilterStrength": 1,
                },
            }
        ],
    )
    destinations = kwargs.get(
        "destinations", [{"Id": "destination.1"}, {"Id": "destination.2"}]
    )
    encoder_settings = kwargs.get(
        "encoder_settings",
        {
            "VideoDescriptions": [],
            "AudioDescriptions": [],
            "OutputGroups": [],
            "TimecodeConfig": {"Source": "a-source"},
        },
    )
    input_specification = kwargs.get("input_specification", {})
    log_level = kwargs.get("log_level", "INFO")
    tags = kwargs.get("tags", {"Customer": "moto"})
    return {
        "Name": name,
        "RoleArn": role_arn,
        "InputAttachments": input_settings,
        "Destinations": destinations,
        "EncoderSettings": encoder_settings,
        "InputSpecification": input_specification,
        "RequestId": name,
        "LogLevel": log_level,
        "Tags": tags,
    }


@pytest.mark.asyncio
async def test_create_channel_succeeds() -> None:
    with mock_aws():
        async with _client() as client:
            channel_config = _create_channel_config("test channel 1")
            response = await client.create_channel(**channel_config)

    assert response["ResponseMetadata"]["HTTPStatusCode"] == 200
    channel = response["Channel"]
    assert channel["Arn"] == f"arn:aws:medialive:channel:{channel['Id']}"
    assert channel["Destinations"] == channel_config["Destinations"]
    assert channel["EncoderSettings"] == channel_config["EncoderSettings"]
    assert channel["InputAttachments"] == channel_config["InputAttachments"]
    assert channel["Name"] == "test channel 1"
    assert channel["State"] == "CREATING"
    assert channel["Tags"]["Customer"] == "moto"


@pytest.mark.asyncio
async def test_list_channels_succeeds() -> None:
    with mock_aws():
        async with _client() as client:
            channel_configs = [
                _create_channel_config(f"test {idx}", request_id=f"req-{idx}")
                for idx in range(10)
            ]
            channel_configs[1]["ChannelClass"] = "SINGLE_PIPELINE"

            for config in channel_configs:
                await client.create_channel(**config)

            response = await client.list_channels()
            page1 = await client.list_channels(MaxResults=2)
            page2 = await client.list_channels(
                MaxResults=5, NextToken=page1["NextToken"]
            )
            page3 = await client.list_channels(NextToken=page2["NextToken"])

    assert len(response["Channels"]) == 10
    assert response["Channels"][0]["Name"] == "test 0"
    assert response["Channels"][0]["ChannelClass"] == "STANDARD"
    assert response["Channels"][0]["PipelinesRunningCount"] == 2
    assert response["Channels"][1]["Name"] == "test 1"
    assert response["Channels"][1]["ChannelClass"] == "SINGLE_PIPELINE"
    assert response["Channels"][1]["PipelinesRunningCount"] == 1

    assert len(page1["Channels"]) == 2
    channel_names = [c["Name"] for c in page1["Channels"]]
    assert sorted(channel_names) == ["test 0", "test 1"]

    assert len(page2["Channels"]) == 5
    channel_names = [c["Name"] for c in page2["Channels"]]
    assert sorted(channel_names) == ["test 2", "test 3", "test 4", "test 5", "test 6"]

    assert len(page3["Channels"]) == 3
    channel_names = [c["Name"] for c in page3["Channels"]]
    assert sorted(channel_names) == ["test 7", "test 8", "test 9"]


@pytest.mark.asyncio
async def test_delete_channel_moves_channel_in_deleted_state() -> None:
    with mock_aws():
        async with _client() as client:
            channel_name = "test channel X"
            channel_config = _create_channel_config(channel_name)
            channel_resp = await client.create_channel(**channel_config)
            channel_id = channel_resp["Channel"]["Id"]
            delete_response = await client.delete_channel(ChannelId=channel_id)

    assert delete_response["Name"] == channel_name
    assert delete_response["State"] == "DELETING"


@pytest.mark.asyncio
async def test_describe_channel_succeeds() -> None:
    with mock_aws():
        async with _client() as client:
            channel_name = "test channel X"
            channel_config = _create_channel_config(channel_name)

            channel_resp = await client.create_channel(**channel_config)
            channel_id = channel_resp["Channel"]["Id"]
            channel = await client.describe_channel(ChannelId=channel_id)

    assert channel["Arn"] == f"arn:aws:medialive:channel:{channel['Id']}"
    assert channel["Destinations"] == channel_config["Destinations"]
    assert channel["EncoderSettings"] == channel_config["EncoderSettings"]
    assert channel["InputAttachments"] == channel_config["InputAttachments"]
    assert channel["Name"] == channel_name
    assert channel["State"] == "IDLE"
    assert channel["Tags"]["Customer"] == "moto"


@pytest.mark.asyncio
async def test_start_channel_succeeds() -> None:
    with mock_aws():
        async with _client() as client:
            channel_name = "testchan1"
            channel_config = _create_channel_config(channel_name)
            channel_id = (await client.create_channel(**channel_config))["Channel"][
                "Id"
            ]

            await client.start_channel(ChannelId=channel_id)
            channel = await client.describe_channel(ChannelId=channel_id)

    assert channel["State"] == "RUNNING"


@pytest.mark.asyncio
async def test_stop_channel_succeeds() -> None:
    with mock_aws():
        async with _client() as client:
            channel_name = "testchan1"
            channel_config = _create_channel_config(channel_name)
            channel_id = (await client.create_channel(**channel_config))["Channel"][
                "Id"
            ]

            await client.start_channel(ChannelId=channel_id)
            await client.stop_channel(ChannelId=channel_id)
            channel = await client.describe_channel(ChannelId=channel_id)

    assert channel["State"] == "IDLE"
