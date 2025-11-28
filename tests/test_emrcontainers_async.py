from __future__ import annotations

from typing import Any, TYPE_CHECKING

import aioboto3
import pytest

from aiomoto import mock_aws


if TYPE_CHECKING:
    from aioboto3.client import ClientCreatorContext


def _client(region: str = "us-east-1") -> ClientCreatorContext[Any]:
    return aioboto3.Session().client("emr-containers", region_name=region)


@pytest.mark.asyncio
async def test_create_and_list_job_runs_async() -> None:
    with mock_aws():
        async with _client() as client:
            virtual_cluster = await client.create_virtual_cluster(
                name="cluster",
                containerProvider={
                    "id": "eks",
                    "type": "EKS",
                    "info": {"eksInfo": {"namespace": "default"}},
                },
            )
            vc_id = virtual_cluster["id"]
            job = await client.start_job_run(
                virtualClusterId=vc_id,
                name="job1",
                executionRoleArn="arn:aws:iam::123456789012:role/EMRContainers-JobExecutionRole",
                releaseLabel="emr-6.7.0-latest",
                jobDriver={"sparkSubmitJobDriver": {"entryPoint": "local:///job.py"}},
            )

            jobs = await client.list_job_runs(virtualClusterId=vc_id)

    assert job["id"]
    assert any(j["id"] == job["id"] for j in jobs["jobRuns"])


@pytest.mark.asyncio
async def test_delete_virtual_cluster_async() -> None:
    with mock_aws():
        async with _client() as client:
            virtual_cluster = await client.create_virtual_cluster(
                name="cluster",
                containerProvider={
                    "id": "eks",
                    "type": "EKS",
                    "info": {"eksInfo": {"namespace": "default"}},
                },
            )
            vc_id = virtual_cluster["id"]
            await client.delete_virtual_cluster(id=vc_id)

            desc = await client.describe_virtual_cluster(id=vc_id)

    assert desc["virtualCluster"]["state"] == "TERMINATED"
