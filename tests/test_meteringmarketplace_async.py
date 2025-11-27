from copy import deepcopy
from datetime import datetime
from typing import TYPE_CHECKING

import aioboto3
import pytest

from aiomoto import mock_aws


if TYPE_CHECKING:
    from aioboto3.client import ClientCreatorContext
    from types_aiobotocore_meteringmarketplace.client import MarketplaceMeteringClient


USAGE_RECORDS = [
    {
        "Timestamp": datetime(2019, 8, 25, 21, 1, 38),
        "CustomerIdentifier": "cust-1",
        "Dimension": "dim-1",
        "Quantity": 6984,
    },
    {
        "Timestamp": datetime(2019, 9, 7, 16, 4, 47),
        "CustomerIdentifier": "cust-2",
        "Dimension": "dim-2",
        "Quantity": 6388,
    },
    {
        "Timestamp": datetime(2019, 6, 15, 23, 17, 49),
        "CustomerIdentifier": "cust-3",
        "Dimension": "dim-3",
        "Quantity": 3532,
    },
    {
        "Timestamp": datetime(2019, 9, 10, 19, 56, 35),
        "CustomerIdentifier": "cust-4",
        "Dimension": "dim-4",
        "Quantity": 9897,
    },
    {
        "Timestamp": datetime(2019, 1, 12, 1, 28, 36),
        "CustomerIdentifier": "cust-5",
        "Dimension": "dim-5",
        "Quantity": 5142,
    },
    {
        "Timestamp": datetime(2019, 8, 5, 18, 27, 41),
        "CustomerIdentifier": "cust-6",
        "Dimension": "dim-6",
        "Quantity": 6503,
    },
    {
        "Timestamp": datetime(2019, 7, 18, 3, 22, 18),
        "CustomerIdentifier": "cust-7",
        "Dimension": "dim-7",
        "Quantity": 5465,
    },
    {
        "Timestamp": datetime(2019, 6, 24, 9, 19, 14),
        "CustomerIdentifier": "cust-8",
        "Dimension": "dim-8",
        "Quantity": 6135,
    },
    {
        "Timestamp": datetime(2019, 9, 28, 20, 29, 5),
        "CustomerIdentifier": "cust-9",
        "Dimension": "dim-9",
        "Quantity": 3416,
    },
    {
        "Timestamp": datetime(2019, 6, 17, 2, 5, 34),
        "CustomerIdentifier": "cust-10",
        "Dimension": "dim-10",
        "Quantity": 2184,
    },
]


def _client() -> "ClientCreatorContext[MarketplaceMeteringClient]":
    return aioboto3.Session().client("meteringmarketplace", region_name="us-east-1")


@mock_aws()
@pytest.mark.asyncio
async def test_batch_meter_usage_async() -> None:
    async with _client() as client:
        res = await client.batch_meter_usage(
            UsageRecords=USAGE_RECORDS, ProductCode="PUFXZLyUElvQvrsG"
        )

    assert len(res["Results"]) == 10

    records_without_time = deepcopy(USAGE_RECORDS)
    for record in records_without_time:
        record.pop("Timestamp")

    for result in res["Results"]:
        usage = result["UsageRecord"]
        usage.pop("Timestamp")
        assert usage in records_without_time
        assert result["MeteringRecordId"]
        assert result["Status"] in {
            "DuplicateRecord",
            "CustomerNotSubscribed",
            "Success",
        }
