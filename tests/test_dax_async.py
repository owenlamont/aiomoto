from typing import Any, TYPE_CHECKING

import aioboto3
from botocore.exceptions import ClientError
from moto.core import DEFAULT_ACCOUNT_ID as ACCOUNT_ID  # type: ignore[attr-defined]
import pytest

from aiomoto import mock_aws


if TYPE_CHECKING:
    from aioboto3.client import ClientCreatorContext


def _client() -> ClientCreatorContext[Any]:
    return aioboto3.Session().client("dax", region_name="us-east-2")


def _role_arn() -> str:
    return (
        f"arn:aws:iam::{ACCOUNT_ID}:role/aws-service-role/"
        "dax.amazonaws.com/AWSServiceRoleForDAX"
    )


@pytest.mark.asyncio
async def test_create_cluster_minimal_async() -> None:
    with mock_aws():
        async with _client() as client:
            created = (
                await client.create_cluster(
                    ClusterName="daxcluster",
                    NodeType="dax.t3.small",
                    ReplicationFactor=3,
                    IamRoleArn=_role_arn(),
                )
            )["Cluster"]

            described = (await client.describe_clusters(ClusterNames=["daxcluster"]))[
                "Clusters"
            ][0]

    for cluster in (created, described):
        assert cluster["ClusterName"] == "daxcluster"
        assert cluster["TotalNodes"] == 3
        assert cluster["IamRoleArn"] == _role_arn()
        assert cluster["Status"] == "creating"


@pytest.mark.asyncio
async def test_create_cluster_invalid_name_async() -> None:
    with mock_aws():
        async with _client() as client:
            with pytest.raises(ClientError) as exc:  # pragma: no branch
                await client.create_cluster(
                    ClusterName="1invalid",
                    NodeType="dax.t3.small",
                    ReplicationFactor=3,
                    IamRoleArn=_role_arn(),
                )

    err = exc.value.response["Error"]
    assert err["Code"] == "InvalidParameterValueException"


@pytest.mark.asyncio
async def test_delete_unknown_cluster_async() -> None:
    with mock_aws():
        async with _client() as client:
            with pytest.raises(ClientError) as exc:  # pragma: no branch
                await client.delete_cluster(ClusterName="missing")

    err = exc.value.response["Error"]
    assert err["Code"] == "ClusterNotFoundFault"
