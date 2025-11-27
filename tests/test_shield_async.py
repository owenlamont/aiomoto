from typing import Any, TYPE_CHECKING

import aioboto3
from botocore.exceptions import ClientError
import pytest

from aiomoto import mock_aws


if TYPE_CHECKING:
    from aioboto3.client import ClientCreatorContext


def _client(region: str) -> "ClientCreatorContext[Any]":
    return aioboto3.Session().client("shield", region_name=region)


@pytest.mark.asyncio
async def test_create_protection_async() -> None:
    with mock_aws():
        async with _client("us-east-1") as client:
            resp = await client.create_protection(
                Name="foobar",
                ResourceArn="arn:aws:cloudfront::123456789012:distribution/foobar",
                Tags=[{"Key": "key1", "Value": "value1"}],
            )
    assert "ProtectionId" in resp


@pytest.mark.asyncio
async def test_create_protection_resource_already_exists_async() -> None:
    with mock_aws():
        async with _client("us-east-1") as client:
            await client.create_protection(
                Name="foobar",
                ResourceArn="arn:aws:cloudfront::123456789012:distribution/foobar",
            )
            with pytest.raises(ClientError) as exc:  # pragma: no branch
                await client.create_protection(
                    Name="foobar",
                    ResourceArn="arn:aws:cloudfront::123456789012:distribution/foobar",
                )
    err = exc.value.response["Error"]
    assert err["Code"] == "ResourceAlreadyExistsException"


@pytest.mark.asyncio
async def test_create_protection_invalid_resource_async() -> None:
    invalid_cases = [
        (
            "arn:aws:dynamodb:us-east-1:123456789012:table/foobar",
            "Unrecognized resource 'table' of service 'dynamodb'.",
        ),
        (
            "arn:aws:sns:us-east-2:123456789012:MyTopic",
            "Relative ID must be in the form '<resource>/<id>'.",
        ),
        (
            "arn:aws:ec2:us-east-1:123456789012:security-group/somesg",
            "Unrecognized resource 'security-group' of service 'ec2'.",
        ),
    ]
    with mock_aws():
        async with _client("us-east-1") as client:
            for arn, message in invalid_cases:
                with pytest.raises(ClientError) as exc:
                    await client.create_protection(Name="foobar", ResourceArn=arn)
                err = exc.value.response["Error"]
                assert err["Code"] == "InvalidResourceException"
                assert err["Message"] == message


@pytest.mark.asyncio
async def test_protect_elastic_ip_async() -> None:
    with mock_aws():
        async with aioboto3.Session().client("ec2", region_name="us-east-1") as ec2:
            eip = await ec2.allocate_address(Domain="vpc")
            allocation_id = eip["AllocationId"]
            eip_arn = (
                f"arn:aws:ec2:us-east-1:123456789012:eip-allocation/{allocation_id}"
            )

        async with _client("us-east-1") as shield:
            await shield.create_protection(Name="foobar", ResourceArn=eip_arn)


@pytest.mark.asyncio
async def test_describe_protection_with_resource_arn_async() -> None:
    with mock_aws():
        async with _client("us-east-1") as client:
            await client.create_protection(
                Name="foobar",
                ResourceArn="arn:aws:cloudfront::123456789012:distribution/foobar",
            )
            resp = await client.describe_protection(
                ResourceArn="arn:aws:cloudfront::123456789012:distribution/foobar"
            )
    protection = resp["Protection"]
    assert "Id" in protection
    assert "Name" in protection
    assert "ResourceArn" in protection
    assert "ProtectionArn" in protection


@pytest.mark.asyncio
async def test_describe_protection_with_protection_id_async() -> None:
    with mock_aws():
        async with _client("us-east-1") as client:
            protection = await client.create_protection(
                Name="foobar",
                ResourceArn="arn:aws:cloudfront::123456789012:distribution/foobar",
            )
            protection_id = protection["ProtectionId"]
            resp = await client.describe_protection(ProtectionId=protection_id)
    protection = resp["Protection"]
    assert "Id" in protection
    assert "Name" in protection
    assert "ResourceArn" in protection
    assert "ProtectionArn" in protection


@pytest.mark.asyncio
async def test_describe_protection_with_both_resource_and_protection_id_async() -> None:
    with mock_aws():
        async with _client("us-east-1") as client:
            with pytest.raises(ClientError) as exc:  # pragma: no branch
                await client.describe_protection(
                    ResourceArn="arn:aws:cloudfront::123456789012:distribution/foobar",
                    ProtectionId="aaaaaaaa-bbbb-cccc-dddd-aaa221177777",
                )
    err = exc.value.response["Error"]
    assert err["Code"] == "InvalidParameterException"


@pytest.mark.asyncio
async def test_describe_protection_resource_doesnot_exist_async() -> None:
    with mock_aws():
        async with _client("us-east-1") as client:
            with pytest.raises(ClientError) as exc:  # pragma: no branch
                await client.describe_protection(
                    ResourceArn="arn:aws:cloudfront::123456789012:distribution/donotexist"
                )
    err = exc.value.response["Error"]
    assert err["Code"] == "ResourceNotFoundException"


@pytest.mark.asyncio
async def test_describe_protection_doesnot_exist_async() -> None:
    with mock_aws():
        async with _client("us-east-1") as client:
            with pytest.raises(ClientError) as exc:  # pragma: no branch
                await client.describe_protection(
                    ProtectionId="aaaaaaaa-bbbb-cccc-dddd-aaa221177777"
                )
    err = exc.value.response["Error"]
    assert err["Code"] == "ResourceNotFoundException"


@pytest.mark.asyncio
async def test_list_protections_async() -> None:
    with mock_aws():
        async with _client("us-east-1") as client:
            await client.create_protection(
                Name="shield1",
                ResourceArn="arn:aws:cloudfront::123456789012:distribution/foobar",
            )
            await client.create_protection(
                Name="shield2",
                ResourceArn=(
                    "arn:aws:elasticloadbalancing:us-east-1:123456789012:"
                    "loadbalancer/foobar"
                ),
            )
            resp = await client.list_protections()
    assert len(resp["Protections"]) == 2


@pytest.mark.asyncio
async def test_list_protections_with_only_resource_arn_async() -> None:
    with mock_aws():
        async with _client("us-east-1") as client:
            await client.create_protection(
                Name="shield1",
                ResourceArn="arn:aws:cloudfront::123456789012:distribution/foobar",
            )
            await client.create_protection(
                Name="shield2",
                ResourceArn=(
                    "arn:aws:elasticloadbalancing:us-east-1:123456789012:"
                    "loadbalancer/foobar"
                ),
            )
            resp = await client.list_protections(
                InclusionFilters={
                    "ResourceArns": [
                        "arn:aws:cloudfront::123456789012:distribution/foobar"
                    ]
                }
            )
    assert len(resp["Protections"]) == 1


@pytest.mark.asyncio
async def test_list_protections_with_only_protection_name_async() -> None:
    with mock_aws():
        async with _client("us-east-1") as client:
            await client.create_protection(
                Name="shield1",
                ResourceArn="arn:aws:cloudfront::123456789012:distribution/foobar",
            )
            await client.create_protection(
                Name="shield1",
                ResourceArn=(
                    "arn:aws:elasticloadbalancing:us-east-1:123456789012:"
                    "loadbalancer/foobar"
                ),
            )
            resp = await client.list_protections(
                InclusionFilters={"ProtectionNames": ["shield1"]}
            )
    assert len(resp["Protections"]) == 2


@pytest.mark.asyncio
async def test_list_protections_with_only_resource_type_async() -> None:
    with mock_aws():
        async with _client("us-east-1") as client:
            await client.create_protection(
                Name="shield1",
                ResourceArn="arn:aws:cloudfront::123456789012:distribution/foobar",
            )
            await client.create_protection(
                Name="shield1",
                ResourceArn=(
                    "arn:aws:elasticloadbalancing:us-east-1:123456789012:"
                    "loadbalancer/foobar"
                ),
            )
            await client.create_protection(
                Name="shield1",
                ResourceArn=(
                    "arn:aws:elasticloadbalancing:us-east-1:123456789012:"
                    "loadbalancer/app/my-load-balancer/1234567890123456"
                ),
            )
            resp_classic_elb = await client.list_protections(
                InclusionFilters={"ResourceTypes": ["CLASSIC_LOAD_BALANCER"]}
            )
            resp_alb = await client.list_protections(
                InclusionFilters={"ResourceTypes": ["APPLICATION_LOAD_BALANCER"]}
            )
            resp_cfront = await client.list_protections(
                InclusionFilters={"ResourceTypes": ["CLOUDFRONT_DISTRIBUTION"]}
            )

    assert len(resp_classic_elb.get("Protections", [])) == 1
    assert len(resp_alb.get("Protections", [])) == 1
    assert len(resp_cfront.get("Protections", [])) == 1
