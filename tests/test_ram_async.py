from __future__ import annotations

from datetime import datetime
import json
import re
from typing import Any, TYPE_CHECKING

import aioboto3
from botocore.exceptions import ClientError
from moto.core import DEFAULT_ACCOUNT_ID as ACCOUNT_ID  # type: ignore[attr-defined]
from moto.ram.utils import (
    AWS_MANAGED_PERMISSIONS,
    format_ram_permission,
    RAM_RESOURCE_TYPES,
)
import pytest

from aiomoto import mock_aws


if TYPE_CHECKING:
    from aioboto3.client import ClientCreatorContext


def _ram_client(region: str = "us-east-1") -> ClientCreatorContext[Any]:
    return aioboto3.Session().client("ram", region_name=region)


def _org_client(region: str = "us-east-1") -> ClientCreatorContext[Any]:
    return aioboto3.Session().client("organizations", region_name=region)


@pytest.mark.asyncio
async def test_create_resource_share_async() -> None:
    with mock_aws():
        async with _ram_client() as client:
            response = await client.create_resource_share(name="test")

            resource = response["resourceShare"]
            assert resource["allowExternalPrincipals"] is True
            assert isinstance(resource["creationTime"], datetime)
            assert isinstance(resource["lastUpdatedTime"], datetime)
            assert resource["name"] == "test"
            assert resource["owningAccountId"] == ACCOUNT_ID
            assert re.match(
                (
                    r"arn:aws:ram:us-east-1:\d{12}:resource-share"
                    r"/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
                ),
                resource["resourceShareArn"],
            )
            assert resource["status"] == "ACTIVE"
            assert "featureSet" not in resource

            response = await client.create_resource_share(
                name="test",
                allowExternalPrincipals=False,
                resourceArns=[
                    f"arn:aws:ec2:us-east-1:{ACCOUNT_ID}:transit-gateway/tgw-123456789"
                ],
            )

            resource = response["resourceShare"]
            assert resource["allowExternalPrincipals"] is False
            assert isinstance(resource["creationTime"], datetime)
            assert isinstance(resource["lastUpdatedTime"], datetime)
            assert resource["name"] == "test"
            assert resource["owningAccountId"] == ACCOUNT_ID
            assert re.match(
                (
                    r"arn:aws:ram:us-east-1:\d{12}:resource-share"
                    r"/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
                ),
                resource["resourceShareArn"],
            )
            assert resource["status"] == "ACTIVE"

            response = await client.get_resource_shares(resourceOwner="SELF")
            assert len(response["resourceShares"]) == 2


@pytest.mark.asyncio
async def test_create_resource_share_errors_async() -> None:
    invalid_arn = "invalid-arn"

    with mock_aws():
        async with _ram_client() as client:
            with pytest.raises(ClientError) as exc:
                await client.create_resource_share(
                    name="test", resourceArns=[invalid_arn]
                )
            err = exc.value
            assert err.operation_name == "CreateResourceShare"
            assert err.response["ResponseMetadata"]["HTTPStatusCode"] == 400
            assert "MalformedArnException" in err.response["Error"]["Code"]
            assert err.response["Error"]["Message"] == (
                "The specified resource ARN invalid-arn is not valid. "
                "Verify the ARN and try again."
            )

            with pytest.raises(ClientError) as exc:
                await client.create_resource_share(
                    name="test", resourceArns=[f"arn:aws:iam::{ACCOUNT_ID}:role/test"]
                )
            err = exc.value
            assert err.operation_name == "CreateResourceShare"
            assert err.response["ResponseMetadata"]["HTTPStatusCode"] == 400
            assert "MalformedArnException" in err.response["Error"]["Code"]
            assert err.response["Error"]["Message"] == (
                "You cannot share the selected resource type."
            )

            with pytest.raises(ClientError) as exc:
                await client.create_resource_share(
                    name="test",
                    principals=["invalid"],
                    resourceArns=[
                        f"arn:aws:ec2:us-east-1:{ACCOUNT_ID}:transit-gateway/tgw-123456789"
                    ],
                )
            err = exc.value
            assert err.operation_name == "CreateResourceShare"
            assert err.response["ResponseMetadata"]["HTTPStatusCode"] == 400
            assert "InvalidParameterException" in err.response["Error"]["Code"]
            assert err.response["Error"]["Message"] == (
                "Principal ID invalid is malformed. Verify the ID and try again."
            )


@pytest.mark.asyncio
async def test_create_resource_share_with_organization_async() -> None:
    with mock_aws():
        async with _org_client() as org, _ram_client() as client:
            org_arn = (await org.create_organization(FeatureSet="ALL"))["Organization"][
                "Arn"
            ]
            root_id = (await org.list_roots())["Roots"][0]["Id"]
            ou_arn = (
                await org.create_organizational_unit(ParentId=root_id, Name="test")
            )["OrganizationalUnit"]["Arn"]

            response = await client.create_resource_share(
                name="test",
                principals=[org_arn],
                resourceArns=[
                    f"arn:aws:ec2:us-east-1:{ACCOUNT_ID}:transit-gateway/tgw-123456789"
                ],
            )

            assert response["resourceShare"]["name"] == "test"

            response = await client.create_resource_share(
                name="test",
                principals=[ou_arn],
                resourceArns=[
                    f"arn:aws:ec2:us-east-1:{ACCOUNT_ID}:transit-gateway/tgw-123456789"
                ],
            )

            assert response["resourceShare"]["name"] == "test"


@pytest.mark.asyncio
async def test_create_resource_share_with_organization_errors_async() -> None:
    with mock_aws():
        async with _org_client() as org, _ram_client() as client:
            await org.create_organization(FeatureSet="ALL")
            root_id = (await org.list_roots())["Roots"][0]["Id"]
            await org.create_organizational_unit(ParentId=root_id, Name="test")

            with pytest.raises(ClientError) as exc:
                await client.create_resource_share(
                    name="test",
                    principals=[
                        f"arn:aws:organizations::{ACCOUNT_ID}:organization/o-unknown"
                    ],
                    resourceArns=[
                        f"arn:aws:ec2:us-east-1:{ACCOUNT_ID}:transit-gateway/tgw-123456789"
                    ],
                )
            err = exc.value
            assert err.operation_name == "CreateResourceShare"
            assert err.response["ResponseMetadata"]["HTTPStatusCode"] == 400
            assert "UnknownResourceException" in err.response["Error"]["Code"]
            assert err.response["Error"]["Message"] == (
                "Organization o-unknown could not be found."
            )

            with pytest.raises(ClientError) as exc:
                await client.create_resource_share(
                    name="test",
                    principals=[
                        f"arn:aws:organizations::{ACCOUNT_ID}:ou/o-unknown/ou-unknown"
                    ],
                    resourceArns=[
                        f"arn:aws:ec2:us-east-1:{ACCOUNT_ID}:transit-gateway/tgw-123456789"
                    ],
                )
            err = exc.value
            assert err.operation_name == "CreateResourceShare"
            assert err.response["ResponseMetadata"]["HTTPStatusCode"] == 400
            assert "UnknownResourceException" in err.response["Error"]["Code"]
            assert err.response["Error"]["Message"] == (
                "OrganizationalUnit ou-unknown in unknown organization "
                "could not be found."
            )


@pytest.mark.asyncio
async def test_get_resource_shares_async() -> None:
    with mock_aws():
        async with _ram_client() as client:
            await client.create_resource_share(name="test")

            response = await client.get_resource_shares(resourceOwner="SELF")

        assert len(response["resourceShares"]) == 1
        resource = response["resourceShares"][0]
        assert resource["allowExternalPrincipals"] is True
        assert isinstance(resource["creationTime"], datetime)
        assert resource["featureSet"] == "STANDARD"
        assert isinstance(resource["lastUpdatedTime"], datetime)
        assert resource["name"] == "test"
        assert resource["owningAccountId"] == ACCOUNT_ID
        assert re.match(
            (
                r"arn:aws:ram:us-east-1:\d{12}:resource-share"
                r"/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
            ),
            resource["resourceShareArn"],
        )
        assert resource["status"] == "ACTIVE"


@pytest.mark.asyncio
async def test_get_resource_shares_errors_async() -> None:
    with mock_aws():
        async with _ram_client() as client:
            with pytest.raises(ClientError) as exc:
                await client.get_resource_shares(resourceOwner="invalid")

    err = exc.value
    assert err.operation_name == "GetResourceShares"
    assert err.response["ResponseMetadata"]["HTTPStatusCode"] == 400
    assert "InvalidParameterException" in err.response["Error"]["Code"]
    assert err.response["Error"]["Message"] == (
        "invalid is not a valid resource owner. "
        "Specify either SELF or OTHER-ACCOUNTS and try again."
    )


@pytest.mark.asyncio
async def test_update_resource_share_async() -> None:
    with mock_aws():
        async with _ram_client() as client:
            arn = (await client.create_resource_share(name="test"))["resourceShare"][
                "resourceShareArn"
            ]

            response = await client.update_resource_share(
                resourceShareArn=arn, name="test-update"
            )

            resource = response["resourceShare"]
            assert resource["allowExternalPrincipals"] is True
            assert resource["name"] == "test-update"
            assert resource["owningAccountId"] == ACCOUNT_ID
            assert re.match(
                (
                    r"arn:aws:ram:us-east-1:\d{12}:resource-share"
                    r"/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
                ),
                resource["resourceShareArn"],
            )
            assert resource["status"] == "ACTIVE"
            assert "featureSet" not in resource
            creation_time = resource["creationTime"]
            assert resource["lastUpdatedTime"] > creation_time

            response = await client.get_resource_shares(resourceOwner="SELF")
            assert len(response["resourceShares"]) == 1


@pytest.mark.asyncio
async def test_update_resource_share_errors_async() -> None:
    with mock_aws():
        async with _ram_client() as client:
            with pytest.raises(ClientError) as exc:
                await client.update_resource_share(
                    resourceShareArn=(
                        f"arn:aws:ram:us-east-1:{ACCOUNT_ID}:resource-share/not-existing"
                    ),
                    name="test-update",
                )

    err = exc.value
    assert err.operation_name == "UpdateResourceShare"
    assert err.response["ResponseMetadata"]["HTTPStatusCode"] == 400
    assert "UnknownResourceException" in err.response["Error"]["Code"]
    assert err.response["Error"]["Message"] == (
        f"ResourceShare arn:aws:ram:us-east-1:{ACCOUNT_ID}"
        ":resource-share/not-existing could not be found."
    )


@pytest.mark.asyncio
async def test_delete_resource_share_async() -> None:
    with mock_aws():
        async with _ram_client() as client:
            arn = (await client.create_resource_share(name="test"))["resourceShare"][
                "resourceShareArn"
            ]

            response = await client.delete_resource_share(resourceShareArn=arn)

            assert response["returnValue"] is True

            response = await client.get_resource_shares(resourceOwner="SELF")
            assert len(response["resourceShares"]) == 1
            resource = response["resourceShares"][0]
            assert resource["status"] == "DELETED"
            creation_time = resource["creationTime"]
            assert resource["lastUpdatedTime"] > creation_time


@pytest.mark.asyncio
async def test_delete_resource_share_errors_async() -> None:
    with mock_aws():
        async with _ram_client() as client:
            with pytest.raises(ClientError) as exc:
                await client.delete_resource_share(
                    resourceShareArn=(
                        f"arn:aws:ram:us-east-1:{ACCOUNT_ID}:resource-share/not-existing"
                    )
                )

    err = exc.value
    assert err.operation_name == "DeleteResourceShare"
    assert err.response["ResponseMetadata"]["HTTPStatusCode"] == 400
    assert "UnknownResourceException" in err.response["Error"]["Code"]
    assert err.response["Error"]["Message"] == (
        f"ResourceShare arn:aws:ram:us-east-1:{ACCOUNT_ID}"
        ":resource-share/not-existing could not be found."
    )


@pytest.mark.asyncio
async def test_enable_sharing_with_aws_organization_async() -> None:
    with mock_aws():
        async with _org_client() as org, _ram_client() as client:
            await org.create_organization(FeatureSet="ALL")

            response = await client.enable_sharing_with_aws_organization()

    assert response["returnValue"] is True


@pytest.mark.asyncio
async def test_enable_sharing_with_aws_organization_errors_async() -> None:
    with mock_aws():
        async with _ram_client() as client:
            with pytest.raises(ClientError) as exc:
                await client.enable_sharing_with_aws_organization()

    err = exc.value
    assert err.operation_name == "EnableSharingWithAwsOrganization"
    assert err.response["ResponseMetadata"]["HTTPStatusCode"] == 400
    assert "OperationNotPermittedException" in err.response["Error"]["Code"]
    assert err.response["Error"]["Message"] == (
        "Unable to enable sharing with AWS Organizations. "
        "Received AccessDeniedException from AWSOrganizations with the "
        "following error message: "
        "You don't have permissions to access this resource."
    )


@pytest.mark.asyncio
async def test_get_resource_share_associations_with_principals_async() -> None:
    with mock_aws():
        async with _ram_client() as client:
            response = await client.create_resource_share(
                name="test",
                principals=["123456789012"],
                resourceArns=[
                    f"arn:aws:ec2:us-east-1:{ACCOUNT_ID}:transit-gateway/tgw-123456789"
                ],
            )
            resource_share_arn = response["resourceShare"]["resourceShareArn"]

            response = await client.get_resource_share_associations(
                associationType="PRINCIPAL", resourceShareArns=[resource_share_arn]
            )

    assert len(response["resourceShareAssociations"]) == 1
    association = response["resourceShareAssociations"][0]
    assert association["resourceShareArn"] == resource_share_arn
    assert association["resourceShareName"] == "test"
    assert association["associatedEntity"] == "123456789012"
    assert association["associationType"] == "PRINCIPAL"
    assert association["status"] == "ASSOCIATED"
    assert isinstance(association["creationTime"], datetime)
    assert isinstance(association["lastUpdatedTime"], datetime)
    assert association["external"] is False


@pytest.mark.asyncio
async def test_get_resource_share_associations_with_resources_async() -> None:
    resource_arn = f"arn:aws:ec2:us-east-1:{ACCOUNT_ID}:transit-gateway/tgw-123456789"

    with mock_aws():
        async with _ram_client() as client:
            response = await client.create_resource_share(
                name="test", principals=["123456789012"], resourceArns=[resource_arn]
            )
            resource_share_arn = response["resourceShare"]["resourceShareArn"]

            response = await client.get_resource_share_associations(
                associationType="RESOURCE", resourceShareArns=[resource_share_arn]
            )

    assert len(response["resourceShareAssociations"]) == 1
    association = response["resourceShareAssociations"][0]
    assert association["resourceShareArn"] == resource_share_arn
    assert association["resourceShareName"] == "test"
    assert association["associatedEntity"] == resource_arn
    assert association["associationType"] == "RESOURCE"
    assert association["status"] == "ASSOCIATED"
    assert isinstance(association["creationTime"], datetime)
    assert isinstance(association["lastUpdatedTime"], datetime)
    assert association["external"] is False


@pytest.mark.asyncio
async def test_get_resource_share_associations_with_filters_async() -> None:
    resource_arn = f"arn:aws:ec2:us-east-1:{ACCOUNT_ID}:transit-gateway/tgw-123456789"

    with mock_aws():
        async with _ram_client() as client:
            await client.create_resource_share(
                name="test", principals=["123456789012"], resourceArns=[resource_arn]
            )

            response = await client.get_resource_share_associations(
                associationType="PRINCIPAL", principal="123456789012"
            )

            assert len(response["resourceShareAssociations"]) == 1
            assert (
                response["resourceShareAssociations"][0]["associatedEntity"]
                == "123456789012"
            )

            response = await client.get_resource_share_associations(
                associationType="RESOURCE", resourceArn=resource_arn
            )

            assert len(response["resourceShareAssociations"]) == 1
            assert (
                response["resourceShareAssociations"][0]["associatedEntity"]
                == resource_arn
            )


@pytest.mark.asyncio
async def test_get_resource_share_associations_errors_async() -> None:
    resource_arn = f"arn:aws:ec2:us-east-1:{ACCOUNT_ID}:transit-gateway/tgw-123456789"

    with mock_aws():
        async with _ram_client() as client:
            await client.create_resource_share(
                name="test", principals=["123456789012"], resourceArns=[resource_arn]
            )

            with pytest.raises(ClientError) as exc:
                await client.get_resource_share_associations(associationType="INVALID")
            err = exc.value
            assert err.operation_name == "GetResourceShareAssociations"
            assert err.response["ResponseMetadata"]["HTTPStatusCode"] == 400
            assert "InvalidParameterException" in err.response["Error"]["Code"]
            assert "is not a valid association type" in err.response["Error"]["Message"]

            with pytest.raises(ClientError) as exc:
                await client.get_resource_share_associations(
                    associationType="PRINCIPAL", associationStatus="INVALID"
                )
            err = exc.value
            assert err.operation_name == "GetResourceShareAssociations"
            assert err.response["ResponseMetadata"]["HTTPStatusCode"] == 400
            assert "InvalidParameterException" in err.response["Error"]["Code"]
            assert (
                "is not a valid association status" in err.response["Error"]["Message"]
            )

            with pytest.raises(ClientError) as exc:
                await client.get_resource_share_associations(
                    associationType="PRINCIPAL", resourceArn=resource_arn
                )
            err = exc.value
            assert err.operation_name == "GetResourceShareAssociations"
            assert err.response["ResponseMetadata"]["HTTPStatusCode"] == 400
            assert "InvalidParameterException" in err.response["Error"]["Code"]
            assert (
                "You cannot specify a resource ARN when the association type is "
                "PRINCIPAL" in err.response["Error"]["Message"]
            )

            with pytest.raises(ClientError) as exc:
                await client.get_resource_share_associations(
                    associationType="RESOURCE", principal="123456789012"
                )
            err = exc.value
            assert err.operation_name == "GetResourceShareAssociations"
            assert err.response["ResponseMetadata"]["HTTPStatusCode"] == 400
            assert "InvalidParameterException" in err.response["Error"]["Code"]
            assert (
                "You cannot specify a principal when the association type is "
                "RESOURCE" in err.response["Error"]["Message"]
            )


@pytest.mark.parametrize(
    ("resource_region_scope", "expect_error", "error_message"),
    [
        ({}, False, None),
        ({"resourceRegionScope": "ALL"}, False, None),
        ({"resourceRegionScope": "GLOBAL"}, False, None),
        ({"resourceRegionScope": "REGIONAL"}, False, None),
        (
            {"resourceRegionScope": "INVALID"},
            True,
            "INVALID is not a valid resource region scope value. "
            "Specify a valid value and try again.",
        ),
    ],
    ids=[
        "default_region_scope",
        "all_region_scope",
        "global_region_scope",
        "regional_region_scope",
        "invalid_region_scope",
    ],
)
@pytest.mark.asyncio
async def test_list_resource_types_async(
    resource_region_scope: dict[str, str], expect_error: bool, error_message: str | None
) -> None:
    region_scope = resource_region_scope.get("resourceRegionScope")

    with mock_aws():
        async with _ram_client() as client:
            if expect_error:
                with pytest.raises(ClientError) as exc:
                    await client.list_resource_types(**resource_region_scope)
                err = exc.value
                assert err.response["ResponseMetadata"]["HTTPStatusCode"] == 400
                assert "InvalidParameterException" in err.response["Error"]["Code"]
                assert err.response["Error"]["Message"] == error_message
                return

            response = await client.list_resource_types(**resource_region_scope)

    expected_types = RAM_RESOURCE_TYPES
    if region_scope == "GLOBAL":
        expected_types = [
            resource_type
            for resource_type in expected_types
            if resource_type["resourceRegionScope"] == "GLOBAL"
        ]
    elif region_scope == "REGIONAL":
        expected_types = [
            resource_type
            for resource_type in expected_types
            if resource_type["resourceRegionScope"] == "REGIONAL"
        ]

    assert "resourceTypes" in response
    assert response["resourceTypes"] == expected_types


@pytest.mark.parametrize(
    ("parameters", "expect_error", "error_message"),
    [
        ({}, False, None),
        ({"resourceType": "glue:catalog"}, False, None),
        ({"permissionType": "ALL"}, False, None),
        ({"resourceType": "glue:catalog", "permissionType": "AWS"}, False, None),
        (
            {"resourceType": "gluE:catalog", "permissionType": "AWS"},
            True,
            "Invalid resource type: gluE:catalog",
        ),
        (
            {"resourceType": "glue:catalog", "permissionType": "INVALID"},
            True,
            "INVALID is not a valid scope. Must be one of: ALL, AWS, LOCAL.",
        ),
    ],
    ids=[
        "default_params",
        "valid_resource_type",
        "valid_permission_type",
        "valid_resource_type_and_permission_type",
        "invalid_resource_type",
        "invalid_permission_type",
    ],
)
@pytest.mark.asyncio
async def test_list_permissions_async(
    parameters: dict[str, str], expect_error: bool, error_message: str | None
) -> None:
    permission_types_relation = {"AWS": "AWS_MANAGED", "LOCAL": "CUSTOMER_MANAGED"}
    resource_type = parameters.get("resourceType")
    permission_type = parameters.get("permissionType")

    with mock_aws():
        async with _ram_client() as client:
            if expect_error:
                with pytest.raises(ClientError) as exc:
                    await client.list_permissions(**parameters)
                err = exc.value
                assert err.response["ResponseMetadata"]["HTTPStatusCode"] == 400
                assert "InvalidParameterException" in err.response["Error"]["Code"]
                assert err.response["Error"]["Message"] == error_message
                return

            response = await client.list_permissions(**parameters)

    expected_permissions = AWS_MANAGED_PERMISSIONS
    if resource_type:
        expected_permissions = [
            permission
            for permission in expected_permissions
            if permission["resourceType"].lower() == resource_type.lower()
        ]

    if permission_type and permission_type != "ALL":
        expected_permissions = [
            permission
            for permission in expected_permissions
            if permission_types_relation.get(permission_type)
            == permission["permissionType"]
        ]

    assert "permissions" in response
    assert json.dumps(response["permissions"], default=str) == json.dumps(
        expected_permissions, default=str
    )


def test_format_ram_permission_defaults() -> None:
    result = format_ram_permission("TestPermission", "test:Resource")
    assert result["name"] == "TestPermission"
    assert result["resourceType"] == "test:Resource"
    assert result["version"] == "1"
    assert result["arn"] == "arn:aws:ram::aws:permission/TestPermission"
    assert result["status"] == "ATTACHABLE"
    assert result["isResourceTypeDefault"] is True
    assert result["permissionType"] == "AWS_MANAGED"
    assert result["defaultVersion"] is True
    assert re.match(
        r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3}", result["creationTime"]
    )
    assert result["creationTime"] == result["lastUpdatedTime"]


def test_format_ram_permission_custom_values() -> None:
    result = format_ram_permission(
        name="CustomPermission",
        resource_type="custom:Type",
        version="2",
        arn_prefix="arn:aws:ram::custom:permission/",
        status="UNATTACHABLE",
        creation_time="2023-01-01 12:00:00.000",
        last_updated_time="2023-01-02 13:00:00.000",
        is_resource_type_default=False,
        permission_type="CUSTOM",
        default_version=False,
    )
    assert result["name"] == "CustomPermission"
    assert result["resourceType"] == "custom:Type"
    assert result["version"] == "2"
    assert result["arn"] == "arn:aws:ram::custom:permission/CustomPermission"
    assert result["status"] == "UNATTACHABLE"
    assert result["creationTime"] == "2023-01-01 12:00:00.000"
    assert result["lastUpdatedTime"] == "2023-01-02 13:00:00.000"
    assert result["isResourceTypeDefault"] is False
    assert result["permissionType"] == "CUSTOM"
    assert result["defaultVersion"] is False


def test_ram_resource_types_structure() -> None:
    for entry in RAM_RESOURCE_TYPES:
        assert "resourceType" in entry
        assert "serviceName" in entry
        assert "resourceRegionScope" in entry
        assert entry["resourceRegionScope"] in ("REGIONAL", "GLOBAL")


def test_aws_managed_permissions_structure() -> None:
    for permission in AWS_MANAGED_PERMISSIONS:
        assert "arn" in permission
        assert permission["arn"].startswith("arn:aws:ram::aws:permission/")
        assert "name" in permission
        assert "resourceType" in permission
        assert "creationTime" in permission
        assert "lastUpdatedTime" in permission
        assert "status" in permission
        assert "permissionType" in permission
        assert permission["permissionType"] == "AWS_MANAGED"
        assert isinstance(permission["isResourceTypeDefault"], bool)
