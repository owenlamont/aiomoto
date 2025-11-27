from __future__ import annotations

from typing import Any, TYPE_CHECKING

import aioboto3
from moto.core import DEFAULT_ACCOUNT_ID  # type: ignore[attr-defined]
import pytest

from aiomoto import mock_aws


if TYPE_CHECKING:
    from aioboto3.client import ClientCreatorContext


def _client() -> ClientCreatorContext[Any]:
    return aioboto3.Session().client("securityhub", region_name="us-east-1")


@pytest.mark.asyncio
async def test_get_findings_async() -> None:
    finding = {
        "AwsAccountId": DEFAULT_ACCOUNT_ID,
        "CreatedAt": "2024-01-01T00:00:00.001Z",
        "UpdatedAt": "2024-01-01T00:00:00.000Z",
        "Description": "Test finding description",
        "GeneratorId": "test-generator",
        "Id": "test-finding-001",
        "ProductArn": (
            f"arn:aws:securityhub:us-east-1:{DEFAULT_ACCOUNT_ID}:"
            f"product/{DEFAULT_ACCOUNT_ID}/default"
        ),
        "Resources": [{"Id": "test-resource", "Type": "AwsEc2Instance"}],
        "SchemaVersion": "2018-10-08",
        "Severity": {"Label": "HIGH"},
        "Title": "Test Finding",
        "Types": ["Software and Configuration Checks"],
    }

    with mock_aws():
        async with _client() as client:
            resp = await client.batch_import_findings(Findings=[finding])
            findings = await client.get_findings()

    assert resp["SuccessCount"] == 1
    assert len(findings["Findings"]) == 1
