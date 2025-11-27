from typing import Any, TYPE_CHECKING

import aioboto3
import pytest

from aiomoto import mock_aws


if TYPE_CHECKING:
    from aioboto3.client import ClientCreatorContext


def _client() -> ClientCreatorContext[Any]:
    return aioboto3.Session().client("directconnect", region_name="us-east-1")


@pytest.mark.asyncio
async def test_create_and_describe_connections_async() -> None:
    with mock_aws():
        async with _client() as client:
            await client.create_connection(
                location="EqDC2",
                bandwidth="10Gbps",
                connectionName="TestConnection1",
                requestMACSec=False,
            )
            await client.create_connection(
                location="EqDC2",
                bandwidth="10Gbps",
                connectionName="TestConnection2",
                requestMACSec=True,
            )

            resp = await client.describe_connections()

    connections = resp["connections"]
    assert len(connections) == 2
    assert connections[0]["connectionState"] == "available"
    assert connections[1]["macSecCapable"] is True


@pytest.mark.asyncio
async def test_delete_connection_async() -> None:
    with mock_aws():
        async with _client() as client:
            conn = await client.create_connection(
                location="EqDC2", bandwidth="10Gbps", connectionName="DeleteMe"
            )

            deleted = await client.delete_connection(connectionId=conn["connectionId"])

    assert deleted["connectionState"] == "deleted"
