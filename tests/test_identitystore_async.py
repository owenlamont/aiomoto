from typing import Any, TYPE_CHECKING
from uuid import UUID, uuid4

import aioboto3
from botocore.exceptions import ClientError
import pytest

from aiomoto import mock_aws


if TYPE_CHECKING:
    from aioboto3.client import ClientCreatorContext


def _client() -> ClientCreatorContext[Any]:
    return aioboto3.Session().client("identitystore", region_name="us-east-2")


def _store_id() -> str:
    return f"d-{uuid4().hex[:10]}"


async def _create_user(client: Any, store_id: str, username: str = "user") -> str:
    resp = await client.create_user(
        IdentityStoreId=store_id,
        UserName=username,
        DisplayName="display",
        Name={"GivenName": "Given", "FamilyName": "Family"},
    )
    return str(resp["UserId"])


@pytest.mark.asyncio
async def test_create_group_and_duplicate_name_async() -> None:
    with mock_aws():
        async with _client() as client:
            store_id = _store_id()
            resp = await client.create_group(
                IdentityStoreId=store_id, DisplayName="test_group", Description="desc"
            )

            assert resp["IdentityStoreId"] == store_id
            assert UUID(resp["GroupId"])

            with pytest.raises(ClientError) as exc:  # pragma: no branch
                await client.create_group(
                    IdentityStoreId=store_id,
                    DisplayName="test_group",
                    Description="desc",
                )

    err = exc.value
    assert err.response["Error"]["Code"] == "ConflictException"
    assert err.response["Error"]["Message"] == "Duplicate GroupDisplayName"


@pytest.mark.asyncio
async def test_create_user_duplicate_username_async() -> None:
    with mock_aws():
        async with _client() as client:
            store_id = _store_id()
            await _create_user(client, store_id, username="dup")

            with pytest.raises(ClientError) as exc:  # pragma: no branch
                await _create_user(client, store_id, username="dup")

    err = exc.value
    assert err.response["Error"]["Code"] == "ConflictException"
    assert err.response["Error"]["Message"] == "Duplicate UserName"


@pytest.mark.asyncio
async def test_group_membership_lifecycle_async() -> None:
    with mock_aws():
        async with _client() as client:
            store_id = _store_id()
            group_id = (
                await client.create_group(
                    IdentityStoreId=store_id, DisplayName="team", Description="desc"
                )
            )["GroupId"]
            user_id = await _create_user(client, store_id, username="member")

            create_resp = await client.create_group_membership(
                IdentityStoreId=store_id, GroupId=group_id, MemberId={"UserId": user_id}
            )

            assert UUID(create_resp["MembershipId"])
            assert create_resp["IdentityStoreId"] == store_id

            list_resp = await client.list_group_memberships(
                IdentityStoreId=store_id, GroupId=group_id
            )
            assert len(list_resp["GroupMemberships"]) == 1
            assert list_resp["GroupMemberships"][0]["MemberId"]["UserId"] == user_id
