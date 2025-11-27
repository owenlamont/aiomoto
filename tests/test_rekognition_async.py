from typing import Any, TYPE_CHECKING
from uuid import uuid4

import aioboto3
import pytest

from aiomoto import mock_aws


if TYPE_CHECKING:
    from aioboto3.client import ClientCreatorContext


def _client(region: str) -> ClientCreatorContext[Any]:
    return aioboto3.Session().client("rekognition", region_name=region)


def _job_id() -> str:
    return (uuid4().hex + uuid4().hex)[:64]


@pytest.mark.asyncio
async def test_start_and_get_face_search_async() -> None:
    with mock_aws():
        async with _client("ap-southeast-1") as client:
            start = await client.start_face_search(
                CollectionId="collection_id",
                Video={"S3Object": {"Bucket": "bucket", "Name": "key"}},
            )
        async with _client("us-east-2") as client:
            resp = await client.get_face_search(JobId=start["JobId"])

    assert resp["JobStatus"] == "SUCCEEDED"


@pytest.mark.asyncio
async def test_detect_labels_and_text_async() -> None:
    with mock_aws():
        async with _client("ap-southeast-1") as client:
            labels = await client.detect_labels(
                Image={"S3Object": {"Bucket": "string", "Name": "name.jpg"}},
                MaxLabels=10,
            )
            text = await client.detect_text(
                Image={"S3Object": {"Bucket": "string", "Name": "name.jpg"}}
            )

    assert "Labels" in labels
    assert "TextDetections" in text


@pytest.mark.asyncio
async def test_detect_custom_labels_async() -> None:
    with mock_aws():
        async with _client("us-east-2") as client:
            resp = await client.detect_custom_labels(
                Image={"S3Object": {"Bucket": "string", "Name": "name.jpg"}},
                MaxResults=10,
                MinConfidence=80,
                ProjectVersionArn=_job_id(),
            )

    assert resp["CustomLabels"][0]["Name"] == "MyLogo"
