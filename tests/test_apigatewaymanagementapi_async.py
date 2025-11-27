from __future__ import annotations

from typing import Any, TYPE_CHECKING

import aioboto3
from moto.apigatewaymanagementapi.models import apigatewaymanagementapi_backends
from moto.core import DEFAULT_ACCOUNT_ID  # type: ignore[attr-defined]
import pytest

from aiomoto import mock_aws


if TYPE_CHECKING:
    from aioboto3.client import ClientCreatorContext


def _client(region: str) -> ClientCreatorContext[Any]:
    return aioboto3.Session().client("apigatewaymanagementapi", region_name=region)


@pytest.mark.asyncio
async def test_get_connection_async() -> None:
    with mock_aws():
        async with _client("us-east-2") as client:
            conn = await client.get_connection(ConnectionId="anything")

    assert "ConnectedAt" in conn
    assert conn["Identity"]["SourceIp"] == "192.168.0.1"


@pytest.mark.asyncio
async def test_post_to_connection_async() -> None:
    region = "ap-southeast-1"
    with mock_aws():
        async with _client(region) as client:
            await client.post_to_connection(ConnectionId="anything", Data=b"first")
            await client.post_to_connection(ConnectionId="anything", Data=b"more")

        backend = apigatewaymanagementapi_backends[DEFAULT_ACCOUNT_ID][region]
        assert backend.connections["anything"].data == b"firstmore"
