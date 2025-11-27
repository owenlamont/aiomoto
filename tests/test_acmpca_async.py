from __future__ import annotations

from typing import Any, TYPE_CHECKING

import aioboto3
from botocore.exceptions import ClientError
from moto.core import DEFAULT_ACCOUNT_ID  # type: ignore[attr-defined]
import pytest

from aiomoto import mock_aws


if TYPE_CHECKING:
    from aioboto3.client import ClientCreatorContext


def _client(region: str) -> ClientCreatorContext[Any]:
    return aioboto3.Session().client("acm-pca", region_name=region)


def _config(common_name: str = "example.com") -> dict[str, Any]:
    return {
        "KeyAlgorithm": "RSA_4096",
        "SigningAlgorithm": "SHA512WITHRSA",
        "Subject": {"CommonName": common_name},
    }


@pytest.mark.asyncio
async def test_create_and_describe_certificate_authority_async() -> None:
    region = "ap-southeast-1"
    with mock_aws():
        async with _client(region) as client:
            arn = (
                await client.create_certificate_authority(
                    CertificateAuthorityConfiguration=_config(),
                    CertificateAuthorityType="SUBORDINATE",
                    IdempotencyToken="token",
                )
            )["CertificateAuthorityArn"]

            ca = (
                await client.describe_certificate_authority(CertificateAuthorityArn=arn)
            )["CertificateAuthority"]

    assert ca["Arn"] == arn
    assert ca["OwnerAccount"] == DEFAULT_ACCOUNT_ID
    assert ca["Status"] == "PENDING_CERTIFICATE"


@pytest.mark.asyncio
async def test_get_certificate_authority_csr_async() -> None:
    with mock_aws():
        async with _client("us-east-2") as client:
            arn = (
                await client.create_certificate_authority(
                    CertificateAuthorityConfiguration=_config("evilcorp.com"),
                    CertificateAuthorityType="ROOT",
                    IdempotencyToken="token",
                )
            )["CertificateAuthorityArn"]

            resp = await client.get_certificate_authority_csr(
                CertificateAuthorityArn=arn
            )

    assert "Csr" in resp


@pytest.mark.asyncio
async def test_get_certificate_authority_certificate_invalid_state_async() -> None:
    with mock_aws():
        async with _client("us-east-1") as client:
            arn = (
                await client.create_certificate_authority(
                    CertificateAuthorityConfiguration=_config(),
                    CertificateAuthorityType="SUBORDINATE",
                    IdempotencyToken="token",
                )
            )["CertificateAuthorityArn"]

            with pytest.raises(ClientError) as exc:  # pragma: no branch
                await client.get_certificate_authority_certificate(
                    CertificateAuthorityArn=arn
                )

    err = exc.value.response["Error"]
    assert err["Code"] == "InvalidStateException"
