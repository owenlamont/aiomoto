from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, TYPE_CHECKING

import aioboto3
from botocore.exceptions import ClientError
import pytest

from aiomoto import mock_aws


if TYPE_CHECKING:
    from aioboto3.client import ClientCreatorContext


def _client() -> ClientCreatorContext[Any]:
    return aioboto3.Session().client("route53domains", region_name="global")


def _route53() -> ClientCreatorContext[Any]:
    return aioboto3.Session().client("route53", region_name="global")


def _domain_params() -> dict[str, Any]:
    contact = {
        "FirstName": "First",
        "LastName": "Last",
        "ContactType": "PERSON",
        "AddressLine1": "address 1",
        "City": "New York City",
        "CountryCode": "US",
        "ZipCode": "123123123",
        "Email": "email@gmail.com",
    }
    return {
        "DomainName": "domain.com",
        "DurationInYears": 3,
        "AutoRenew": True,
        "AdminContact": contact,
        "RegistrantContact": contact,
        "TechContact": contact,
        "PrivacyProtectAdminContact": True,
        "PrivacyProtectRegistrantContact": True,
        "PrivacyProtectTechContact": True,
    }


@pytest.mark.asyncio
async def test_register_domain_and_operations_async() -> None:
    with mock_aws():
        async with _client() as dom_client, _route53() as r53_client:
            res = await dom_client.register_domain(**_domain_params())
            op_id = res["OperationId"]

            operations = (await dom_client.list_operations(Type=["REGISTER_DOMAIN"]))[
                "Operations"
            ]
            assert any(op["OperationId"] == op_id for op in operations)

            zones = await r53_client.list_hosted_zones()
            assert "domain.com" in [z["Name"] for z in zones["HostedZones"]]

            future = datetime.now(timezone.utc) + timedelta(minutes=1)
            ops_future = await dom_client.list_operations(
                SubmittedSince=future.timestamp()
            )
            assert ops_future["Operations"] == []

            detail = await dom_client.get_operation_detail(OperationId=op_id)
            assert detail["Status"] == "SUCCESSFUL"


@pytest.mark.asyncio
async def test_register_domain_invalid_input_async() -> None:
    with mock_aws():
        async with _client() as dom_client, _route53() as r53_client:
            params = _domain_params()
            params["DomainName"] = "a"
            params["DurationInYears"] = 500
            with pytest.raises(ClientError) as exc:
                await dom_client.register_domain(**params)

            err = exc.value.response["Error"]
            assert err["Code"] == "InvalidInput"
            assert (await r53_client.list_hosted_zones())["HostedZones"] == []

            with pytest.raises(ClientError):  # pragma: no branch
                await dom_client.list_operations(Type=["INVALID_TYPE"])
