from typing import Any, TYPE_CHECKING

import aioboto3
from botocore.exceptions import ClientError
import pytest

from aiomoto import mock_aws


if TYPE_CHECKING:
    from aioboto3.client import ClientCreatorContext


ENCRYPTION_POLICY = """
{
    "Rules":[
        {
            "ResourceType":"collection",
            "Resource":[
                "collection/col-foobar",
                "collection/col-foobar1"
            ]
        }
    ],
    "AWSOwnedKey":false,
    "KmsARN":"arn:aws:kms:ap-southeast-1:123456789012:key/4c1731d6-5435-ed4d-be13-d53411a7cfbd"
}
"""

NETWORK_POLICY = """
[{
    "Rules":[
        {
            "ResourceType":"collection",
            "Resource":[
                "collection/nwk-foobar5"
            ]
        }
    ],
    "AllowFromPublic":false,
    "SourceVPCEs":[
        "vpce-03cf101d15c3bff53"
    ]
}]
"""


def _client() -> "ClientCreatorContext[Any]":
    return aioboto3.Session().client(
        "opensearchserverless", region_name="ap-southeast-1"
    )


@mock_aws()
@pytest.mark.asyncio
async def test_create_security_policy_async() -> None:
    async with _client() as client:
        resp = await client.create_security_policy(
            description="Encryption policy for foobar collection",
            name="policy-foobar",
            policy=ENCRYPTION_POLICY,
            type="encryption",
        )

    detail = resp["securityPolicyDetail"]
    assert detail["name"] == "policy-foobar"
    assert "createdDate" in detail
    assert "policyVersion" in detail
    assert detail["type"] == "encryption"


@pytest.mark.asyncio
async def test_create_security_policy_invalid_type_async() -> None:
    with mock_aws():
        async with _client() as client:
            with pytest.raises(ClientError) as exc:  # pragma: no branch
                await client.create_security_policy(
                    name="policy-foobar", policy=ENCRYPTION_POLICY, type="fake type"
                )
    assert exc.value.response["Error"]["Code"] == "ValidationException"


@pytest.mark.asyncio
async def test_create_security_policy_same_name_and_type_async() -> None:
    with mock_aws():
        async with _client() as client:
            await client.create_security_policy(
                name="policy-foobar", policy=ENCRYPTION_POLICY, type="encryption"
            )
            with pytest.raises(ClientError) as exc:  # pragma: no branch
                await client.create_security_policy(
                    name="policy-foobar", policy=ENCRYPTION_POLICY, type="encryption"
                )
    assert exc.value.response["Error"]["Code"] == "ConflictException"


@pytest.mark.asyncio
async def test_get_security_policy_async() -> None:
    with mock_aws():
        async with _client() as client:
            await client.create_security_policy(
                description="Encryption policy for foobar collection",
                name="policy-foobar",
                policy=ENCRYPTION_POLICY,
                type="encryption",
            )
            resp = await client.get_security_policy(
                name="policy-foobar", type="encryption"
            )

    sp_detail = resp["securityPolicyDetail"]
    assert sp_detail["name"] == "policy-foobar"
    assert sp_detail["type"] == "encryption"
    assert "policyVersion" in sp_detail


@pytest.mark.asyncio
async def test_get_security_policy_invalid_name_async() -> None:
    with mock_aws():
        async with _client() as client:
            await client.create_security_policy(
                name="policy-foo", policy=ENCRYPTION_POLICY, type="encryption"
            )
            with pytest.raises(ClientError) as exc:  # pragma: no branch
                await client.get_security_policy(name="policy-bar", type="encryption")

    assert exc.value.response["Error"]["Code"] == "ResourceNotFoundException"


@pytest.mark.asyncio
async def test_list_security_policies_async() -> None:
    with mock_aws():
        async with _client() as client:
            await client.create_security_policy(
                name="policy-foobar1", policy=NETWORK_POLICY, type="network"
            )
            await client.create_security_policy(
                name="policy-foobar2", policy=NETWORK_POLICY, type="network"
            )
            resp = await client.list_security_policies(type="network")

    assert len(resp["securityPolicySummaries"]) == 2


@pytest.mark.asyncio
async def test_list_security_policies_with_resource_async() -> None:
    with mock_aws():
        async with _client() as client:
            await client.create_security_policy(
                name="policy-foobar1", policy=NETWORK_POLICY, type="network"
            )
            await client.create_security_policy(
                name="policy-foobar2", policy=NETWORK_POLICY, type="network"
            )
            resp = await client.list_security_policies(
                resource=["collection/nwk-foobar4", "collection/nwk-foobar5"],
                type="network",
            )

    assert len(resp["securityPolicySummaries"]) == 2
