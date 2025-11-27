from typing import Any, TYPE_CHECKING

import aioboto3
import pytest

from aiomoto import mock_aws


if TYPE_CHECKING:
    from aioboto3.client import ClientCreatorContext


def _client() -> ClientCreatorContext[Any]:
    return aioboto3.Session().client("lexv2-models", region_name="us-east-1")


@pytest.mark.asyncio
async def test_create_and_list_bot_locales_async() -> None:
    with mock_aws():
        async with _client() as client:
            bot = await client.create_bot(
                botName="bot1",
                roleArn="arn:aws:iam::123456789012:role/service-role/lex-bot-role",
                dataPrivacy={"childDirected": False},
                idleSessionTTLInSeconds=300,
            )
            bots = await client.list_bots()

    assert any(b["botId"] == bot["botId"] for b in bots.get("botSummaries", []))
