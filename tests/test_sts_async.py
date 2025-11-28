from __future__ import annotations

from datetime import datetime
import json

import aioboto3
from botocore.exceptions import ClientError
from freezegun import freeze_time
from moto.sts.responses import MAX_FEDERATION_TOKEN_POLICY_LENGTH, MAX_ROLE_NAME_LENGTH
import pytest

from aiomoto import mock_aws


ACCOUNT_ID = "123456789012"

REGION_PARTITIONS = [
    ("us-east-1", "aws"),
    ("cn-north-1", "aws-cn"),
    ("us-isob-east-1", "aws-iso-b"),
]


def _session() -> aioboto3.Session:
    return aioboto3.Session()


@pytest.mark.asyncio
async def test_get_session_token_async() -> None:
    with freeze_time("2012-01-01 12:00:00", real_asyncio=True), mock_aws():
        async with _session().client("sts", region_name="us-east-1") as sts:
            creds = (await sts.get_session_token(DurationSeconds=903))["Credentials"]

    assert isinstance(creds["Expiration"], datetime)
    assert creds["Expiration"].strftime("%Y-%m-%dT%H:%M:%S.000Z") == (
        "2012-01-01T12:15:03.000Z"
    )
    assert creds["SessionToken"] == (
        "AQoEXAMPLEH4aoAH0gNCAPyJxz4BlCFFxWNE1OPTgk5TthT+FvwqnKwRcOIfrR"
        "h3c/LTo6UDdyJwOOvEVPvLXCrrrUtdnniCEXAMPLE/IvU1dYUg2RVAJBanLiHb"
        "4IgRmpRV3zrkuWJOgQs8IZZaIv2BXIa2R4OlgkBN9bkUDNCJiBeb/AXlzBBko7"
        "b15fjrBs2+cTQtpZ3CYWFXG8C5zqx37wnOE49mRl/+OtkIKGO7fAE"
    )
    assert creds["AccessKeyId"] == "AKIAIOSFODNN7EXAMPLE"
    assert creds["SecretAccessKey"] == "wJalrXUtnFEMI/K7MDENG/bPxRfiCYzEXAMPLEKEY"


@pytest.mark.asyncio
async def test_get_federation_token_async() -> None:
    federated_user_name = "sts-user"
    with freeze_time("2012-01-01 12:00:00", real_asyncio=True), mock_aws():
        async with _session().client("sts", region_name="us-east-1") as sts:
            fed_token = await sts.get_federation_token(
                DurationSeconds=903, Name=federated_user_name
            )
    creds = fed_token["Credentials"]
    fed_user = fed_token["FederatedUser"]

    assert isinstance(creds["Expiration"], datetime)
    assert creds["Expiration"].strftime("%Y-%m-%dT%H:%M:%S.000Z") == (
        "2012-01-01T12:15:03.000Z"
    )
    assert creds["SessionToken"] == (
        "AQoDYXdzEPT//////////wEXAMPLEtc764bNrC9SAPBSM22wDOk4x4HIZ8j4FZ"
        "TwdQWLWsKWHGBuFqwAeMicRXmxfpSPfIeoIYRqTflfKD8YUuwthAx7mSEI/qkP"
        "pKPi/kMcGdQrmGdeehM4IC1NtBmUpp2wUE8phUZampKsburEDy0KPkyQDYwT7W"
        "Z0wq5VSXDvp75YU9HFvlRd8Tx6q6fE8YQcHNVXAkiY9q6d+xo0rKwT38xVqr7Z"
        "D0u0iPPkUL64lIZbqBAz+scqKmlzm8FDrypNC9Yjc8fPOLn9FX9KSYvKTr4rvx"
        "3iSIlTJabIQwj2ICCR/oLxBA=="
    )
    assert creds["AccessKeyId"] == "AKIAIOSFODNN7EXAMPLE"
    assert creds["SecretAccessKey"] == "wJalrXUtnFEMI/K7MDENG/bPxRfiCYzEXAMPLEKEY"
    assert fed_user["Arn"] == (
        f"arn:aws:sts::{ACCOUNT_ID}:federated-user/{federated_user_name}"
    )
    assert fed_user["FederatedUserId"] == f"{ACCOUNT_ID}:{federated_user_name}"


@pytest.mark.asyncio
@pytest.mark.parametrize(("region", "partition"), REGION_PARTITIONS)
async def test_assume_role_async(region: str, partition: str) -> None:
    with freeze_time("2012-01-01 12:00:00", real_asyncio=True), mock_aws():
        async with _session().client("iam", region_name=region) as iam:
            trust_policy_document = {
                "Version": "2012-10-17",
                "Statement": {
                    "Effect": "Allow",
                    "Principal": {"AWS": f"arn:aws:iam::{ACCOUNT_ID}:root"},
                    "Action": "sts:AssumeRole",
                },
            }
            role = (
                await iam.create_role(
                    RoleName="test-role",
                    AssumeRolePolicyDocument=json.dumps(trust_policy_document),
                )
            )["Role"]
            role_arn = role["Arn"]
            role_id = role["RoleId"]

        async with _session().client("sts", region_name=region) as sts:
            assume_role_response = await sts.assume_role(
                RoleArn=role_arn,
                RoleSessionName="session-name",
                Policy=json.dumps(
                    {
                        "Statement": [
                            {
                                "Sid": "Stmt13690092345534",
                                "Action": ["S3:ListBucket"],
                                "Effect": "Allow",
                                "Resource": ["arn:aws:s3:::foobar-tester"],
                            }
                        ]
                    }
                ),
                DurationSeconds=900,
            )

    credentials = assume_role_response["Credentials"]
    assert credentials["Expiration"].isoformat() == "2012-01-01T12:15:00+00:00"
    assert len(credentials["SessionToken"]) == 356
    assert credentials["SessionToken"].startswith("FQoGZXIvYXdzE")
    assert len(credentials["AccessKeyId"]) == 20
    assert credentials["AccessKeyId"].startswith("ASIA")
    assert len(credentials["SecretAccessKey"]) == 40

    assumed = assume_role_response["AssumedRoleUser"]
    assert assumed["Arn"] == (
        f"arn:{partition}:sts::{ACCOUNT_ID}:assumed-role/test-role/session-name"
    )
    assert assumed["AssumedRoleId"].startswith("AROA")
    assert assumed["AssumedRoleId"].rpartition(":")[0] == role_id
    assert assumed["AssumedRoleId"].endswith(":session-name")


@pytest.mark.asyncio
async def test_assume_role_with_too_long_role_session_name_async() -> None:
    with mock_aws():
        async with _session().client("iam", region_name="us-east-1") as iam:
            trust_policy_document = {
                "Version": "2012-10-17",
                "Statement": {
                    "Effect": "Allow",
                    "Principal": {"AWS": f"arn:aws:iam::{ACCOUNT_ID}:root"},
                    "Action": "sts:AssumeRole",
                },
            }
            role_arn = (
                await iam.create_role(
                    RoleName="test-role",
                    AssumeRolePolicyDocument=json.dumps(trust_policy_document),
                )
            )["Role"]["Arn"]

        async with _session().client("sts", region_name="us-east-1") as sts:
            session_name = "s" * 65
            with pytest.raises(ClientError) as ex:  # pragma: no branch
                await sts.assume_role(
                    RoleArn=role_arn, RoleSessionName=session_name, DurationSeconds=900
                )

    assert ex.value.response["Error"]["Code"] == "ValidationError"
    assert str(MAX_ROLE_NAME_LENGTH) in ex.value.response["Error"]["Message"]
    assert session_name in ex.value.response["Error"]["Message"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("region", "partition"), [("us-east-1", "aws"), ("cn-north-1", "aws-cn")]
)
async def test_get_caller_identity_with_default_credentials_async(
    region: str, partition: str
) -> None:
    with mock_aws():
        async with _session().client("sts", region_name=region) as sts:
            identity = await sts.get_caller_identity()

    assert identity["Arn"] == f"arn:{partition}:sts::{ACCOUNT_ID}:user/moto"
    assert identity["UserId"] == "AKIAIOSFODNN7EXAMPLE"
    assert identity["Account"] == str(ACCOUNT_ID)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("region", "partition"), [("us-east-1", "aws"), ("cn-north-1", "aws-cn")]
)
async def test_get_caller_identity_with_iam_user_credentials_async(
    region: str, partition: str
) -> None:
    with mock_aws():
        async with _session().client("iam", region_name=region) as iam:
            iam_user = (await iam.create_user(UserName="new-user"))["User"]
            access_key = (await iam.create_access_key(UserName="new-user"))["AccessKey"]

        async with _session().client(
            "sts",
            region_name=region,
            aws_access_key_id=access_key["AccessKeyId"],
            aws_secret_access_key=access_key["SecretAccessKey"],
        ) as sts:
            identity = await sts.get_caller_identity()

    assert identity["Arn"] == iam_user["Arn"]
    assert identity["UserId"] == iam_user["UserId"]
    assert identity["Account"] == str(ACCOUNT_ID)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("region", "partition"), [("us-east-1", "aws"), ("cn-north-1", "aws-cn")]
)
async def test_get_caller_identity_with_assumed_role_credentials_async(
    region: str, partition: str
) -> None:
    with mock_aws():
        async with _session().client("iam", region_name=region) as iam:
            trust_policy_document = {
                "Version": "2012-10-17",
                "Statement": {
                    "Effect": "Allow",
                    "Principal": {"AWS": f"arn:aws:iam::{ACCOUNT_ID}:root"},
                    "Action": "sts:AssumeRole",
                },
            }
            iam_role_arn = (
                await iam.create_role(
                    RoleName="new-user",
                    AssumeRolePolicyDocument=json.dumps(trust_policy_document),
                )
            )["Role"]["Arn"]

        async with _session().client("sts", region_name=region) as sts:
            assumed_role = await sts.assume_role(
                RoleArn=iam_role_arn, RoleSessionName="new-session"
            )
            access_key = assumed_role["Credentials"]

        async with _session().client(
            "sts",
            region_name=region,
            aws_access_key_id=access_key["AccessKeyId"],
            aws_secret_access_key=access_key["SecretAccessKey"],
        ) as sts:
            identity = await sts.get_caller_identity()

    assert identity["Arn"] == assumed_role["AssumedRoleUser"]["Arn"]
    assert identity["UserId"] == assumed_role["AssumedRoleUser"]["AssumedRoleId"]
    assert identity["Account"] == str(ACCOUNT_ID)


@pytest.mark.asyncio
async def test_federation_token_with_too_long_policy_async() -> None:
    with mock_aws():
        async with _session().client("sts", region_name="us-east-1") as sts:
            resource_tmpl = (
                "arn:aws:s3:::yyyy-xxxxx-cloud-default/"
                "my_default_folder/folder-name-%s/*"
            )
            statements = [
                {
                    "Effect": "Allow",
                    "Action": ["s3:*"],
                    "Resource": resource_tmpl % str(num),
                }
                for num in range(30)
            ]
            json_policy = json.dumps({"Version": "2012-10-17", "Statement": statements})
            assert len(json_policy) > MAX_FEDERATION_TOKEN_POLICY_LENGTH

            with pytest.raises(ClientError) as ex:  # pragma: no branch
                await sts.get_federation_token(
                    Name="foo", DurationSeconds=3600, Policy=json_policy
                )

    assert ex.value.response["Error"]["Code"] == "ValidationError"
    message = ex.value.response["Error"]["Message"]
    assert str(MAX_FEDERATION_TOKEN_POLICY_LENGTH) in message
