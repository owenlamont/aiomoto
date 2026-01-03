from __future__ import annotations

import aioboto3
from botocore.exceptions import ClientError
import pytest

from aiomoto import mock_aws


ACCOUNT_ID = "123456789012"


def _session() -> aioboto3.Session:
    return aioboto3.Session()


@pytest.mark.asyncio
async def test_create_key_without_description_async() -> None:
    with mock_aws():
        async with _session().client("kms", region_name="us-east-1") as kms:
            metadata = (await kms.create_key(Policy="my policy"))["KeyMetadata"]

    assert metadata["AWSAccountId"] == ACCOUNT_ID
    assert metadata["Description"] == ""
    assert "KeyId" in metadata
    assert "Arn" in metadata


@pytest.mark.asyncio
async def test_create_key_with_invalid_key_spec_async() -> None:
    unsupported_key_spec = "NotSupportedKeySpec"
    with mock_aws():
        async with _session().client("kms", region_name="us-east-1") as kms:
            with pytest.raises(ClientError) as ex:  # pragma: no branch
                await kms.create_key(Policy="my policy", KeySpec=unsupported_key_spec)

    err = ex.value.response["Error"]
    assert err["Code"] == "ValidationException"
    assert unsupported_key_spec in err["Message"]


@pytest.mark.asyncio
async def test_create_key_async() -> None:
    with mock_aws():
        async with _session().client("kms", region_name="us-east-1") as kms:
            symmetric = await kms.create_key(
                Policy="my policy",
                Description="my key",
                KeyUsage="ENCRYPT_DECRYPT",
                Tags=[{"TagKey": "project", "TagValue": "moto"}],
            )

            rsa_encrypt = await kms.create_key(
                KeyUsage="ENCRYPT_DECRYPT", KeySpec="RSA_2048"
            )

            rsa_sign = await kms.create_key(KeyUsage="SIGN_VERIFY", KeySpec="RSA_2048")

            ecc_sign = await kms.create_key(
                KeyUsage="SIGN_VERIFY", KeySpec="ECC_SECG_P256K1"
            )

    sym_meta = symmetric["KeyMetadata"]
    assert (
        sym_meta["Arn"] == f"arn:aws:kms:us-east-1:{ACCOUNT_ID}:key/{sym_meta['KeyId']}"
    )
    assert sym_meta["AWSAccountId"] == ACCOUNT_ID
    assert sym_meta["CustomerMasterKeySpec"] == "SYMMETRIC_DEFAULT"
    assert sym_meta["KeySpec"] == "SYMMETRIC_DEFAULT"
    assert sym_meta["Description"] == "my key"
    assert sym_meta["Enabled"] is True
    assert sym_meta["EncryptionAlgorithms"] == ["SYMMETRIC_DEFAULT"]
    assert sym_meta["KeyManager"] == "CUSTOMER"
    assert sym_meta["KeyState"] == "Enabled"
    assert sym_meta["KeyUsage"] == "ENCRYPT_DECRYPT"
    assert sym_meta["Origin"] == "AWS_KMS"
    assert "SigningAlgorithms" not in sym_meta

    rsa_encrypt_algos = sorted(rsa_encrypt["KeyMetadata"]["EncryptionAlgorithms"])
    assert rsa_encrypt_algos == ["RSAES_OAEP_SHA_1", "RSAES_OAEP_SHA_256"]
    assert "SigningAlgorithms" not in rsa_encrypt["KeyMetadata"]

    rsa_sign_algos = sorted(rsa_sign["KeyMetadata"]["SigningAlgorithms"])
    assert rsa_sign_algos == [
        "RSASSA_PKCS1_V1_5_SHA_256",
        "RSASSA_PKCS1_V1_5_SHA_384",
        "RSASSA_PKCS1_V1_5_SHA_512",
        "RSASSA_PSS_SHA_256",
        "RSASSA_PSS_SHA_384",
        "RSASSA_PSS_SHA_512",
    ]

    ecc_sign_algos = ecc_sign["KeyMetadata"]["SigningAlgorithms"]
    assert ecc_sign_algos == ["ECDSA_SHA_256"]


@pytest.mark.asyncio
async def test_create_multi_region_key_async() -> None:
    with mock_aws():
        async with _session().client("kms", region_name="us-east-1") as kms:
            key = await kms.create_key(
                Policy="my policy",
                Description="my key",
                KeyUsage="ENCRYPT_DECRYPT",
                MultiRegion=True,
                Tags=[{"TagKey": "project", "TagValue": "moto"}],
            )

    meta = key["KeyMetadata"]
    assert meta["KeyId"].startswith("mrk-")
    assert meta["MultiRegion"] is True


@pytest.mark.asyncio
async def test_non_multi_region_key_has_no_multi_region_properties_async() -> None:
    with mock_aws():
        async with _session().client("kms", region_name="us-east-1") as kms:
            key = await kms.create_key(
                Policy="my policy",
                Description="my key",
                KeyUsage="ENCRYPT_DECRYPT",
                MultiRegion=False,
                Tags=[{"TagKey": "project", "TagValue": "moto"}],
            )

    meta = key["KeyMetadata"]
    assert not meta["KeyId"].startswith("mrk-")
    assert meta["MultiRegion"] is False
