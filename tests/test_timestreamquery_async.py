from typing import Any, TYPE_CHECKING

import aioboto3
from botocore.exceptions import ClientError
from moto.core import DEFAULT_ACCOUNT_ID  # type: ignore[attr-defined]
import pytest

from aiomoto import mock_aws


if TYPE_CHECKING:
    from aioboto3.client import ClientCreatorContext


def _client(region: str = "us-east-2") -> ClientCreatorContext[Any]:
    return aioboto3.Session().client("timestream-query", region_name=region)


def _target_config() -> dict[str, Any]:
    return {
        "TimestreamConfiguration": {
            "DatabaseName": "mydb",
            "TableName": "mytab",
            "TimeColumn": "tc",
            "DimensionMappings": [],
        }
    }


@pytest.mark.asyncio
async def test_create_and_delete_scheduled_query_async() -> None:
    with mock_aws():
        async with _client() as client:
            arn = (
                await client.create_scheduled_query(
                    Name="myquery",
                    QueryString="SELECT *",
                    ScheduleConfiguration={"ScheduleExpression": "* * * * * 1"},
                    NotificationConfiguration={
                        "SnsConfiguration": {"TopicArn": "arn:some:topic"}
                    },
                    TargetConfiguration=_target_config(),
                    ScheduledQueryExecutionRoleArn="some role",
                    ErrorReportConfiguration={
                        "S3Configuration": {"BucketName": "error-bucket"}
                    },
                    KmsKeyId="arn:kms:key",
                )
            )["Arn"]

            desc = await client.describe_scheduled_query(ScheduledQueryArn=arn)
            await client.delete_scheduled_query(ScheduledQueryArn=arn)
            with pytest.raises(ClientError):  # pragma: no branch
                await client.describe_scheduled_query(ScheduledQueryArn=arn)

    expected = (
        f"arn:aws:timestream:us-east-2:{DEFAULT_ACCOUNT_ID}:scheduled-query/myquery"
    )
    assert arn == expected
    assert desc["ScheduledQuery"]["Name"] == "myquery"
