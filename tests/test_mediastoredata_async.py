from __future__ import annotations

from typing import Any, TYPE_CHECKING

import aioboto3
from botocore.exceptions import ClientError
import pytest

from aiomoto import mock_aws


if TYPE_CHECKING:
    from aioboto3.client import ClientCreatorContext


def _client() -> ClientCreatorContext[Any]:
    return aioboto3.Session().client("mediastore-data", region_name="us-east-1")


@pytest.mark.asyncio
async def test_put_and_get_object_async() -> None:
    with mock_aws():
        async with _client() as client:
            with pytest.raises(ClientError):
                await client.put_object(Path="/hello.txt", Body=b"hello")
