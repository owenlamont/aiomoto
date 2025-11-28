from __future__ import annotations

from typing import Any, TYPE_CHECKING

import aioboto3
from botocore.exceptions import ParamValidationError
import pytest

from aiomoto import mock_aws


if TYPE_CHECKING:
    from aioboto3.client import ClientCreatorContext


def _client(region: str = "us-east-1") -> ClientCreatorContext[Any]:
    return aioboto3.Session().client("iot-data", region_name=region)


@pytest.mark.asyncio
async def test_publish_and_get_thing_shadow_async() -> None:
    with mock_aws():
        async with aioboto3.Session().client("iot", region_name="us-east-1") as iot:
            await iot.create_thing(thingName="thing1")
        async with _client() as client:
            await client.update_thing_shadow(
                thingName="thing1", payload=b'{"state": {"desired": {"temp": 20}}}'
            )
            resp = await client.get_thing_shadow(thingName="thing1")

    assert await resp["payload"].read()


@pytest.mark.asyncio
async def test_update_thing_shadow_invalid_async() -> None:
    with mock_aws():
        async with aioboto3.Session().client("iot", region_name="us-east-1") as iot:
            await iot.create_thing(thingName="thing1")
        async with _client() as client:
            with pytest.raises(ParamValidationError):  # pragma: no branch
                await client.update_thing_shadow(thingName="", payload=b"{}")
