from __future__ import annotations

from typing import Any, TYPE_CHECKING

import aioboto3
import pytest

from aiomoto import mock_aws


if TYPE_CHECKING:
    from aioboto3.client import ClientCreatorContext


def _client(region: str = "us-east-1") -> ClientCreatorContext[Any]:
    return aioboto3.Session().client("emr-serverless", region_name=region)


@pytest.mark.asyncio
async def test_create_and_start_application_async() -> None:
    with mock_aws():
        async with _client() as client:
            app = await client.create_application(
                name="app1", releaseLabel="emr-6.9.0", type="SPARK"
            )
            await client.start_application(applicationId=app["applicationId"])
            desc = await client.get_application(applicationId=app["applicationId"])

    assert desc["application"]["name"] == "app1"
    assert desc["application"]["state"] in {"STARTED", "STOPPED"}


@pytest.mark.asyncio
async def test_delete_application_async() -> None:
    with mock_aws():
        async with _client() as client:
            app = await client.create_application(
                name="app2", releaseLabel="emr-6.9.0", type="SPARK"
            )
            await client.stop_application(applicationId=app["applicationId"])
            await client.delete_application(applicationId=app["applicationId"])

            desc = await client.get_application(applicationId=app["applicationId"])

    assert desc["application"]["state"] == "TERMINATED"
