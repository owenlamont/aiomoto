from __future__ import annotations

from typing import Any, TYPE_CHECKING

import aioboto3
import pytest

from aiomoto import mock_aws


if TYPE_CHECKING:
    from aioboto3.client import ClientCreatorContext


def _client(region: str = "us-east-1") -> ClientCreatorContext[Any]:
    return aioboto3.Session().client("elasticbeanstalk", region_name=region)


@pytest.mark.asyncio
async def test_create_application_and_environment_async() -> None:
    with mock_aws():
        async with _client() as client:
            app = await client.create_application(ApplicationName="myapp")
            env = await client.create_environment(
                ApplicationName="myapp",
                EnvironmentName="env1",
                SolutionStackName="64bit Amazon Linux 2018.03 v2.9.6 running PHP 7.2",
            )

    assert app["Application"]["ApplicationName"] == "myapp"
    assert env["EnvironmentName"] == "env1"
