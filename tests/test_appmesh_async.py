from __future__ import annotations

from typing import Any, TYPE_CHECKING

import aioboto3
import pytest

from aiomoto import mock_aws


if TYPE_CHECKING:
    from aioboto3.client import ClientCreatorContext


def _client() -> ClientCreatorContext[Any]:
    return aioboto3.Session().client("appmesh", region_name="us-east-1")


@pytest.mark.asyncio
async def test_create_and_list_meshes_async() -> None:
    with mock_aws():
        async with _client() as client:
            await client.create_mesh(
                meshName="mesh1",
                spec={
                    "egressFilter": {"type": "DROP_ALL"},
                    "serviceDiscovery": {"ipPreference": "IPv4_ONLY"},
                },
            )
            await client.create_mesh(
                meshName="mesh2",
                spec={
                    "egressFilter": {"type": "ALLOW_ALL"},
                    "serviceDiscovery": {"ipPreference": "IPv4_PREFERRED"},
                },
            )

            meshes = (await client.list_meshes())["meshes"]

    names = {mesh["meshName"] for mesh in meshes}
    assert names == {"mesh1", "mesh2"}


@pytest.mark.asyncio
async def test_update_and_describe_mesh_async() -> None:
    with mock_aws():
        async with _client() as client:
            await client.create_mesh(
                meshName="mesh1", spec={"egressFilter": {"type": "DROP_ALL"}}
            )

            await client.update_mesh(
                meshName="mesh1", spec={"egressFilter": {"type": "ALLOW_ALL"}}
            )

            mesh = (await client.describe_mesh(meshName="mesh1"))["mesh"]

    assert mesh["meshName"] == "mesh1"
    assert mesh["spec"]["egressFilter"]["type"] == "ALLOW_ALL"
