from __future__ import annotations

import aioboto3
import pytest

from aiomoto import mock_aws


REGION = "us-east-1"
ACCOUNT_ID = "123456789012"


def _session() -> aioboto3.Session:
    return aioboto3.Session()


@pytest.mark.asyncio
async def test_put_rule_async() -> None:
    with mock_aws():
        async with _session().client("events", region_name=REGION) as events:
            response = await events.put_rule(
                Name="my-schedule",
                ScheduleExpression="rate(5 minutes)",
                State="ENABLED",
            )

    assert response["RuleArn"] == (
        f"arn:aws:events:{REGION}:{ACCOUNT_ID}:rule/my-schedule"
    )


@pytest.mark.asyncio
async def test_put_rule_with_event_bus_arn_async() -> None:
    bus_name = "custom-bus"
    bus_arn = f"arn:aws:events:{REGION}:{ACCOUNT_ID}:event-bus/{bus_name}"
    with mock_aws():
        async with _session().client("events", region_name=REGION) as events:
            await events.create_event_bus(Name=bus_name)
            response = await events.put_rule(
                Name="bus-rule",
                EventBusName=bus_arn,
                EventPattern='{"source": ["aws.ec2"]}',
            )

    assert response["RuleArn"] == (
        f"arn:aws:events:{REGION}:{ACCOUNT_ID}:rule/{bus_name}/bus-rule"
    )


@pytest.mark.asyncio
async def test_list_and_describe_rules_async() -> None:
    with mock_aws():
        async with _session().client("events", region_name=REGION) as events:
            await events.put_rule(Name="one", ScheduleExpression="rate(1 minute)")
            await events.put_rule(Name="two", EventPattern='{"detail-type": ["test"]}')

            listed = (await events.list_rules())["Rules"]
            described = await events.describe_rule(Name="one")

    names = {rule["Name"] for rule in listed}
    assert {"one", "two"} <= names
    assert described["Name"] == "one"
    assert described["ScheduleExpression"] == "rate(1 minute)"
