from __future__ import annotations

from typing import Any, TYPE_CHECKING

import aioboto3
import pytest

from aiomoto import mock_aws


if TYPE_CHECKING:
    from aioboto3.client import ClientCreatorContext


def _client() -> ClientCreatorContext[Any]:
    return aioboto3.Session().client("connectcampaigns", region_name="us-east-1")


@pytest.mark.asyncio
async def test_create_and_list_campaigns_async() -> None:
    with mock_aws():
        async with _client() as client:
            await client.create_campaign(
                name="cmp",
                connectInstanceId="arn:aws:connect:us-east-1:123:instance/abc",
                dialerConfig={"predictiveDialerConfig": {"bandwidthAllocation": 0.1}},
                outboundCallConfig={
                    "connectContactFlowId": "flow-id",
                    "connectQueueId": "queue-id",
                    "connectSourcePhoneNumber": "+1234567",
                },
            )
            resp = await client.list_campaigns()

    assert any(c["name"] == "cmp" for c in resp.get("campaignSummaryList", []))


@pytest.mark.asyncio
async def test_delete_campaign_async() -> None:
    with mock_aws():
        async with _client() as client:
            created = await client.create_campaign(
                name="cmp2",
                connectInstanceId="arn:aws:connect:us-east-1:123:instance/abc",
                dialerConfig={"predictiveDialerConfig": {"bandwidthAllocation": 0.1}},
                outboundCallConfig={
                    "connectContactFlowId": "flow-id",
                    "connectQueueId": "queue-id",
                    "connectSourcePhoneNumber": "+1234567",
                },
            )

            await client.delete_campaign(id=created["id"])
            resp = await client.list_campaigns()

    assert all(c["id"] != created["id"] for c in resp.get("campaignSummaryList", []))
