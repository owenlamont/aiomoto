from typing import Any, TYPE_CHECKING

import aioboto3
from botocore.exceptions import ClientError
import pytest

from aiomoto import mock_aws


if TYPE_CHECKING:
    from aioboto3.client import ClientCreatorContext


def _client(region: str = "us-east-1") -> ClientCreatorContext[Any]:
    return aioboto3.Session().client("cognito-identity", region_name=region)


@pytest.mark.asyncio
async def test_create_and_describe_identity_pool_async() -> None:
    with mock_aws():
        async with _client() as client:
            pool = await client.create_identity_pool(
                IdentityPoolName="mypool", AllowUnauthenticatedIdentities=False
            )
            described = await client.describe_identity_pool(
                IdentityPoolId=pool["IdentityPoolId"]
            )

    assert described["IdentityPoolName"] == "mypool"


@pytest.mark.asyncio
async def test_get_open_id_token_for_developer_identity_async() -> None:
    with mock_aws():
        async with _client() as client:
            pool = await client.create_identity_pool(
                IdentityPoolName="devpool", AllowUnauthenticatedIdentities=True
            )
            token = await client.get_open_id_token_for_developer_identity(
                IdentityPoolId=pool["IdentityPoolId"],
                Logins={"login.provider.com": "user"},
            )

    assert "Token" in token


@pytest.mark.asyncio
async def test_delete_identity_pool_async() -> None:
    with mock_aws():
        async with _client() as client:
            pool = await client.create_identity_pool(
                IdentityPoolName="deletepool", AllowUnauthenticatedIdentities=True
            )
            await client.delete_identity_pool(IdentityPoolId=pool["IdentityPoolId"])

            with pytest.raises(ClientError):  # pragma: no branch
                await client.describe_identity_pool(
                    IdentityPoolId=pool["IdentityPoolId"]
                )
