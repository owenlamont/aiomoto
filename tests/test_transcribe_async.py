from typing import Any, TYPE_CHECKING

import aioboto3
import pytest

from aiomoto import mock_aws


if TYPE_CHECKING:
    from aioboto3.client import ClientCreatorContext


def _client() -> ClientCreatorContext[Any]:
    return aioboto3.Session().client("transcribe", region_name="us-east-1")


@pytest.mark.asyncio
async def test_run_medical_transcription_job_async() -> None:
    args = {
        "MedicalTranscriptionJobName": "MyJob",
        "LanguageCode": "en-US",
        "Media": {"MediaFileUri": "s3://my-bucket/my-media-file.wav"},
        "OutputBucketName": "my-output-bucket",
        "Specialty": "PRIMARYCARE",
        "Type": "CONVERSATION",
    }

    with mock_aws():
        async with _client() as client:
            resp = await client.start_medical_transcription_job(**args)
            for _ in range(3):
                resp = await client.get_medical_transcription_job(
                    MedicalTranscriptionJobName="MyJob"
                )
            await client.delete_medical_transcription_job(
                MedicalTranscriptionJobName="MyJob"
            )

    assert resp["MedicalTranscriptionJob"]["TranscriptionJobStatus"] in {
        "COMPLETED",
        "IN_PROGRESS",
        "QUEUED",
    }
