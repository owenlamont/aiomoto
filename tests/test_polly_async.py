from typing import Any, TYPE_CHECKING

import aioboto3
import pytest

from aiomoto import mock_aws


if TYPE_CHECKING:
    from aioboto3.client import ClientCreatorContext


def _client() -> ClientCreatorContext[Any]:
    return aioboto3.Session().client("polly", region_name="us-east-1")


@pytest.mark.asyncio
async def test_synthesize_speech_async() -> None:
    with mock_aws():
        async with _client() as client:
            resp = await client.synthesize_speech(
                OutputFormat="mp3", VoiceId="Joanna", Text="hello world"
            )

    body = await resp["AudioStream"].read()
    assert isinstance(body, (bytes, bytearray))
    assert resp["ContentType"] == "audio/mpeg"


@pytest.mark.asyncio
async def test_synthesize_with_engine_param_async() -> None:
    with mock_aws():
        async with _client() as client:
            resp = await client.synthesize_speech(
                OutputFormat="mp3", VoiceId="Joanna", Text="hello", Engine="standard"
            )

    assert await resp["AudioStream"].read()
