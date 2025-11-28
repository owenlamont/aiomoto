from __future__ import annotations

from typing import Any, TYPE_CHECKING

import aioboto3
from botocore.exceptions import ClientError
import pytest

from aiomoto import mock_aws


if TYPE_CHECKING:
    from aioboto3.client import ClientCreatorContext


def _client(region: str) -> ClientCreatorContext[Any]:
    return aioboto3.Session().client("service-quotas", region_name=region)


@pytest.mark.asyncio
async def test_list_aws_default_service_quotas_async() -> None:
    with mock_aws():
        async with _client("eu-west-1") as client:
            resp = await client.list_aws_default_service_quotas(ServiceCode="vpc")

    assert len(resp["Quotas"]) == 25
    quotas = resp["Quotas"]
    assert any(q["QuotaCode"] == "L-2AFB9258" and q["Value"] == 5.0 for q in quotas)
    assert any(q["QuotaCode"] == "L-F678F1CE" and q["Value"] == 5.0 for q in quotas)


@pytest.mark.asyncio
async def test_list_defaults_for_unknown_service_async() -> None:
    with mock_aws():
        async with _client("us-east-1") as client:
            with pytest.raises(ClientError) as exc:  # pragma: no branch
                await client.list_aws_default_service_quotas(ServiceCode="unknown")

    err = exc.value.response["Error"]
    assert err["Code"] == "NoSuchResourceException"
    assert err["Message"].startswith(
        "This service is not available in the current Region"
    )


@pytest.mark.asyncio
async def test_get_service_quota_async() -> None:
    with mock_aws():
        async with _client("us-east-2") as client:
            quotas = (await client.list_aws_default_service_quotas(ServiceCode="vpc"))[
                "Quotas"
            ]

            for quota in quotas:
                resp = await client.get_service_quota(
                    ServiceCode="vpc", QuotaCode=quota["QuotaCode"]
                )
                assert quota == resp["Quota"]


@pytest.mark.asyncio
async def test_get_unknown_service_quota_async() -> None:
    with mock_aws():
        async with _client("us-east-2") as client:
            with pytest.raises(ClientError) as exc:  # pragma: no branch
                await client.get_service_quota(ServiceCode="vpc", QuotaCode="unknown")

    err = exc.value.response["Error"]
    assert err["Code"] == "NoSuchResourceException"
