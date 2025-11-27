from typing import Any, TYPE_CHECKING

import aioboto3
import pytest

from aiomoto import mock_aws


if TYPE_CHECKING:
    from aioboto3.client import ClientCreatorContext


def _client() -> ClientCreatorContext[Any]:
    return aioboto3.Session().client("transfer", region_name="us-east-1")


async def _create_server(client: Any) -> str:
    resp = await client.create_server(
        Certificate="mock_certificate",
        Domain="S3",
        EndpointDetails={
            "AddressAllocationIds": ["allocation_1", "allocation_2"],
            "SubnetIds": ["subnet_1", "subnet_2"],
            "VpcEndpointId": "mock_vpc_endpoint_id_1",
            "VpcId": "mock_vpc_id",
            "SecurityGroupIds": ["mock_sg_id_1", "mock_sg_id_2"],
        },
        EndpointType="VPC",
        HostKey="ED25519",
        IdentityProviderDetails={
            "Url": "mock_url",
            "InvocationRole": "mock_invocation_role",
            "DirectoryId": "mock_directory_id",
            "Function": "mock_function",
            "SftpAuthenticationMethods": "PUBLIC_KEY_AND_PASSWORD",
        },
        IdentityProviderType="AWS_DIRECTORY_SERVICE",
        LoggingRole="mock_logging_role",
        PostAuthenticationLoginBanner="mock_post_authentication_login_banner",
        PreAuthenticationLoginBanner="mock_pre_authentication_login_banner",
        Protocols=["FTPS", "FTP", "SFTP"],
        ProtocolDetails={
            "PassiveIp": "mock_passive_ip",
            "TlsSessionResumptionMode": "ENABLED",
            "SetStatOption": "ENABLE_NO_OP",
            "As2Transports": ["HTTP"],
        },
        SecurityPolicyName="mock_security_policy_name",
        StructuredLogDestinations=[
            "structured_log_destinations_1",
            "structured_log_destinations_2",
        ],
        S3StorageOptions={"DirectoryListingOptimization": "ENABLED"},
        Tags=[{"Key": "Owner", "Value": "MotoUser1337"}],
        WorkflowDetails={
            "OnUpload": [
                {
                    "WorkflowId": "mock_upload_workflow_id",
                    "ExecutionRole": "mock_upload_execution_role",
                }
            ]
        },
    )
    return str(resp["ServerId"])


@pytest.mark.asyncio
async def test_create_and_describe_server_async() -> None:
    with mock_aws():
        async with _client() as client:
            server_id = await _create_server(client)
            desc = await client.describe_server(ServerId=server_id)

    assert desc["Server"]["ServerId"] == server_id


@pytest.mark.asyncio
async def test_delete_server_async() -> None:
    with mock_aws():
        async with _client() as client:
            server_id = await _create_server(client)
            await client.delete_server(ServerId=server_id)
            with pytest.raises(KeyError):  # pragma: no branch
                await client.describe_server(ServerId=server_id)
