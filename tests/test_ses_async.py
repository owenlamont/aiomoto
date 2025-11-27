import aioboto3
from aiobotocore.session import AioSession
import boto3
from botocore.exceptions import ClientError
import pytest

from aiomoto import mock_aws


AWS_REGION = "us-east-1"


@pytest.mark.asyncio
async def test_send_email_async_shared_with_boto3() -> None:
    with mock_aws():
        sync = boto3.client("ses", region_name=AWS_REGION)
        sync.verify_domain_identity(Domain="example.com")

        async with AioSession().create_client("ses", region_name=AWS_REGION) as ses:
            response = await ses.send_email(
                Source="sender@example.com",
                Destination={"ToAddresses": ["to@example.com"]},
                Message={
                    "Subject": {"Data": "hello"},
                    "Body": {"Text": {"Data": "body"}},
                },
            )

        assert isinstance(response.get("MessageId"), str)

        quota = sync.get_send_quota()
        assert float(quota["SentLast24Hours"]) >= 1


@pytest.mark.asyncio
async def test_verify_identity_visible_to_sync_and_aioboto3() -> None:
    with mock_aws():
        async with AioSession().create_client("ses", region_name=AWS_REGION) as ses:
            await ses.verify_email_identity(EmailAddress="async@example.com")
            identities = await ses.list_identities()
            assert "async@example.com" in identities["Identities"]

            sync = boto3.client("ses", region_name=AWS_REGION)
            assert "async@example.com" in sync.list_identities()["Identities"]

            async with aioboto3.Session().client("ses", region_name=AWS_REGION) as ses3:
                identities_aioboto3 = await ses3.list_identities()

            assert "async@example.com" in identities_aioboto3["Identities"]


@pytest.mark.asyncio
async def test_unverified_source_rejected() -> None:
    with mock_aws():
        async with AioSession().create_client("ses", region_name=AWS_REGION) as ses:
            with pytest.raises(ClientError) as exc:
                await ses.send_email(
                    Source="unverified@example.com",
                    Destination={"ToAddresses": ["dest@example.com"]},
                    Message={
                        "Subject": {"Data": "hi"},
                        "Body": {"Text": {"Data": "body"}},
                    },
                )

        error = exc.value.response["Error"]
        assert error["Code"] == "MessageRejected"
