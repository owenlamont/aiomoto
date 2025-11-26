from io import BytesIO
import json
from typing import Any
import zipfile

import aioboto3
import pytest

from aiomoto import mock_aws


LAMBDA_REGION = "us-west-2"
PYTHON_VERSION = "3.11"
FUNCTION_NAME = "test-function-123"


def _session() -> aioboto3.Session:
    return aioboto3.Session()


def _lambda_zip() -> bytes:
    buff = BytesIO()
    with zipfile.ZipFile(buff, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "lambda_function.py",
            "def lambda_handler(event, context):\n"
            "    return event or 'Simple Lambda happy path OK'\n",
        )
    return buff.getvalue()


@pytest.mark.asyncio
async def test_run_function_async() -> None:
    with mock_aws(config={"lambda": {"use_docker": False}}):
        async with _session().client("iam", region_name=LAMBDA_REGION) as iam:
            role_arn = await _create_role(iam)
        async with _session().client("lambda", region_name=LAMBDA_REGION) as client:
            await _create_function(client, role_arn)
            result = await client.invoke(FunctionName=FUNCTION_NAME, LogType="Tail")

    assert result["StatusCode"] == 200
    payload = await result["Payload"].read()
    assert payload.decode("utf-8") == "Simple Lambda happy path OK"


@pytest.mark.asyncio
async def test_run_function_no_log_async() -> None:
    payload = {"results": "results"}
    with mock_aws(config={"lambda": {"use_docker": False}}):
        async with _session().client("iam", region_name=LAMBDA_REGION) as iam:
            role_arn = await _create_role(iam)
        async with _session().client("lambda", region_name=LAMBDA_REGION) as client:
            await _create_function(client, role_arn)

            first = await client.invoke(
                FunctionName=FUNCTION_NAME, Payload=json.dumps(payload)
            )
            second = await client.invoke(FunctionName=FUNCTION_NAME)

    assert first["StatusCode"] == 200
    first_payload = await first["Payload"].read()
    assert json.loads(first_payload.decode("utf-8")) == payload
    assert second["StatusCode"] == 200
    second_payload = await second["Payload"].read()
    assert second_payload.decode("utf-8") == "Simple Lambda happy path OK"


async def _create_function(client: Any, role_arn: str) -> None:
    zip_content = _lambda_zip()
    await client.create_function(
        FunctionName=FUNCTION_NAME,
        Runtime=PYTHON_VERSION,
        Role=role_arn,
        Handler="lambda_function.lambda_handler",
        Code={"ZipFile": zip_content},
        Description="test lambda function",
        Timeout=3,
        MemorySize=128,
        Publish=True,
    )


async def _create_role(iam_client: Any) -> str:
    assume_role_policy = json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"Service": "lambda.amazonaws.com"},
                    "Action": "sts:AssumeRole",
                }
            ],
        }
    )
    role = await iam_client.create_role(
        RoleName="lambda-role", AssumeRolePolicyDocument=assume_role_policy
    )
    return str(role["Role"]["Arn"])
