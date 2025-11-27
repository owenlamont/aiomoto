from typing import Any, TYPE_CHECKING

import aioboto3
from botocore.exceptions import ClientError
import pytest

from aiomoto import mock_aws


pytestmark = pytest.mark.filterwarnings(
    "ignore:datetime.datetime.utcnow:DeprecationWarning"
)


if TYPE_CHECKING:
    from aioboto3.client import ClientCreatorContext


ADMIN_ACCOUNT_ID = "111111111111"
MEMBER_ACCOUNT_ID = "222222222222"
REGION = "us-east-1"


def _macie() -> ClientCreatorContext[Any]:
    return aioboto3.Session().client("macie2", region_name=REGION)


def _sts() -> ClientCreatorContext[Any]:
    return aioboto3.Session().client("sts", region_name=REGION)


async def _member_identity() -> dict[str, str]:
    async with _sts() as sts:
        resp = await sts.assume_role(
            RoleArn=f"arn:aws:iam::{MEMBER_ACCOUNT_ID}:role/my-role",
            RoleSessionName="test-session",
        )
    creds = resp["Credentials"]
    return {
        "AccessKeyId": str(creds["AccessKeyId"]),
        "SecretAccessKey": str(creds["SecretAccessKey"]),
        "SessionToken": str(creds["SessionToken"]),
    }


@pytest.mark.asyncio
async def test_get_macie_session_async() -> None:
    with mock_aws():
        async with _macie() as admin:
            response = await admin.get_macie_session()

    assert response["status"] == "ENABLED"
    assert response["findingPublishingFrequency"] == "FIFTEEN_MINUTES"


@pytest.mark.asyncio
async def test_enable_and_disable_macie_async() -> None:
    with mock_aws():
        async with _macie() as admin:
            await admin.disable_macie()
            await admin.enable_macie(
                findingPublishingFrequency="ONE_HOUR", status="ENABLED"
            )
            session = await admin.get_macie_session()

            await admin.disable_macie()
            invitations = await admin.list_invitations()

    assert session["status"] == "ENABLED"
    assert session["findingPublishingFrequency"] == "ONE_HOUR"
    assert invitations["invitations"] == []


@pytest.mark.asyncio
async def test_invitation_flow_async() -> None:
    with mock_aws():
        creds = await _member_identity()
        async with _macie() as admin:
            await admin.create_invitations(accountIds=[MEMBER_ACCOUNT_ID])
            inv_id = (await admin.list_invitations())["invitations"][0]["invitationId"]

            member_session = aioboto3.Session(
                aws_access_key_id=creds["AccessKeyId"],
                aws_secret_access_key=creds["SecretAccessKey"],
                aws_session_token=creds["SessionToken"],
            )
            async with member_session.client("macie2", region_name=REGION) as member:
                await member.accept_invitation(
                    administratorAccountId=ADMIN_ACCOUNT_ID, invitationId=inv_id
                )
                admin_acc = await member.get_administrator_account()

            members = await admin.list_members()
            await admin.delete_member(id=MEMBER_ACCOUNT_ID)

    assert admin_acc["administrator"]["accountId"] == ADMIN_ACCOUNT_ID
    assert members["members"][0]["accountId"] == MEMBER_ACCOUNT_ID


@pytest.mark.asyncio
async def test_get_macie_session_after_disable_async() -> None:
    with mock_aws():
        async with _macie() as admin:
            await admin.disable_macie()
            with pytest.raises(ClientError) as exc:  # pragma: no branch
                await admin.get_macie_session()

    err = exc.value.response["Error"]
    assert err["Code"] == "ResourceNotFoundException"
