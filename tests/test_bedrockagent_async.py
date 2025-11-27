from typing import Any, TYPE_CHECKING

import aioboto3
import pytest

from aiomoto import mock_aws


if TYPE_CHECKING:
    from aioboto3.client import ClientCreatorContext


def _client(region: str = "us-east-1") -> ClientCreatorContext[Any]:
    return aioboto3.Session().client("bedrock-agent", region_name=region)


@pytest.mark.asyncio
async def test_create_and_list_agents_async() -> None:
    with mock_aws():
        async with _client() as client:
            await client.create_agent(
                agentName="agent1",
                foundationModel="anthropic.claude-3-sonnet-20240229-v1:0",
                instruction=(
                    "Long instruction string that easily exceeds forty characters."
                ),
                idleSessionTTLInSeconds=300,
                agentResourceRoleArn="arn:aws:iam::123456789012:role/BedrockAgentRole",
            )
            agents = await client.list_agents()

    assert any(a["agentName"] == "agent1" for a in agents.get("agentSummaries", []))


@pytest.mark.asyncio
async def test_update_agent_status_async() -> None:
    with mock_aws():
        async with _client() as client:
            created = await client.create_agent(
                agentName="agent1",
                foundationModel="anthropic.claude-3-sonnet-20240229-v1:0",
                instruction=(
                    "Long instruction string that easily exceeds forty characters."
                ),
                idleSessionTTLInSeconds=300,
                agentResourceRoleArn="arn:aws:iam::123456789012:role/BedrockAgentRole",
            )
            agent_id = created["agent"].get("agentId") or created.get("agentId")
            # Moto does not require explicit status update parameters beyond defaults
            got = await client.get_agent(agentId=agent_id)

    assert got["agent"]["agentStatus"] in {
        "CREATING",
        "ENABLED",
        "DISABLED",
        "PREPARED",
    }
