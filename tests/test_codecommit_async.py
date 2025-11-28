from __future__ import annotations

from typing import TYPE_CHECKING

import aioboto3
from botocore.exceptions import ClientError
import pytest


if TYPE_CHECKING:
    from aioboto3.client import ClientCreatorContext
    from types_aiobotocore_codecommit.client import (
        CodeCommitClient as AioCodeCommitClient,
    )

from aiomoto import mock_aws


REGION = "eu-central-1"
ACCOUNT_ID = "123456789012"
INVALID_NAME_MESSAGE = (
    "The repository name is not valid. Repository names can be any valid "
    "combination of letters, numbers, periods, underscores, and dashes "
    "between 1 and 100 characters in length. Names are case sensitive. "
    "For more information, see Limits in the AWS CodeCommit User Guide. "
)


def _session() -> aioboto3.Session:
    return aioboto3.Session()


def _client(region: str = REGION) -> ClientCreatorContext[AioCodeCommitClient]:
    return _session().client("codecommit", region_name=region)


@mock_aws()
@pytest.mark.asyncio
async def test_create_repository_async() -> None:
    async with _client() as client:
        metadata = (
            await client.create_repository(
                repositoryName="repository_one",
                repositoryDescription="description repo one",
            )
        )["repositoryMetadata"]

    assert metadata["creationDate"] is not None
    assert metadata["lastModifiedDate"] is not None
    assert metadata["repositoryId"] is not None
    assert metadata["repositoryName"] == "repository_one"
    assert metadata["repositoryDescription"] == "description repo one"
    assert (
        metadata["cloneUrlSsh"]
        == "ssh://git-codecommit.eu-central-1.amazonaws.com/v1/repos/repository_one"
    )
    assert (
        metadata["cloneUrlHttp"]
        == "https://git-codecommit.eu-central-1.amazonaws.com/v1/repos/repository_one"
    )
    assert (
        metadata["Arn"]
        == f"arn:aws:codecommit:eu-central-1:{ACCOUNT_ID}:repository_one"
    )
    assert metadata["accountId"] == ACCOUNT_ID


@pytest.mark.asyncio
async def test_create_repository_without_description_async() -> None:
    with mock_aws():
        async with _client() as client:
            metadata = (
                await client.create_repository(repositoryName="repository_two")
            )["repositoryMetadata"]

    assert metadata.get("repositoryName") == "repository_two"
    assert metadata.get("repositoryDescription") is None

    assert metadata["creationDate"] is not None
    assert metadata["lastModifiedDate"] is not None
    assert metadata["repositoryId"] is not None
    assert (
        metadata["cloneUrlSsh"]
        == "ssh://git-codecommit.eu-central-1.amazonaws.com/v1/repos/repository_two"
    )
    assert (
        metadata["cloneUrlHttp"]
        == "https://git-codecommit.eu-central-1.amazonaws.com/v1/repos/repository_two"
    )
    assert (
        metadata["Arn"]
        == f"arn:aws:codecommit:eu-central-1:{ACCOUNT_ID}:repository_two"
    )
    assert metadata["accountId"] == ACCOUNT_ID


@pytest.mark.asyncio
async def test_create_repository_repository_name_exists_async() -> None:
    with mock_aws():
        async with _client() as client:
            await client.create_repository(repositoryName="repository_two")

            with pytest.raises(ClientError) as err:  # pragma: no branch
                await client.create_repository(
                    repositoryName="repository_two",
                    repositoryDescription="description repo two",
                )

    ex = err.value
    assert ex.operation_name == "CreateRepository"
    assert ex.response["ResponseMetadata"]["HTTPStatusCode"] == 400
    assert ex.response["Error"]["Code"] == "RepositoryNameExistsException"
    assert (
        ex.response["Error"]["Message"]
        == "Repository named repository_two already exists"
    )


@pytest.mark.asyncio
async def test_create_repository_invalid_repository_name_async() -> None:
    with mock_aws():
        async with _client() as client:
            with pytest.raises(ClientError) as err:  # pragma: no branch
                await client.create_repository(
                    repositoryName="in_123_valid_@#$_characters"
                )

    ex = err.value
    assert ex.operation_name == "CreateRepository"
    assert ex.response["ResponseMetadata"]["HTTPStatusCode"] == 400
    assert ex.response["Error"]["Code"] == "InvalidRepositoryNameException"
    assert ex.response["Error"]["Message"] == INVALID_NAME_MESSAGE


@pytest.mark.asyncio
async def test_get_repository_async() -> None:
    with mock_aws():
        async with _client() as client:
            repository_name = "repository_one"

            await client.create_repository(
                repositoryName=repository_name,
                repositoryDescription="description repo one",
            )

            metadata = (await client.get_repository(repositoryName=repository_name))[
                "repositoryMetadata"
            ]

    assert metadata["creationDate"] is not None
    assert metadata["lastModifiedDate"] is not None
    assert metadata["repositoryId"] is not None
    assert metadata["repositoryName"] == repository_name
    assert metadata["repositoryDescription"] == "description repo one"
    assert (
        metadata["cloneUrlSsh"]
        == "ssh://git-codecommit.eu-central-1.amazonaws.com/v1/repos/repository_one"
    )
    assert (
        metadata["cloneUrlHttp"]
        == "https://git-codecommit.eu-central-1.amazonaws.com/v1/repos/repository_one"
    )
    assert (
        metadata["Arn"]
        == f"arn:aws:codecommit:eu-central-1:{ACCOUNT_ID}:repository_one"
    )
    assert metadata["accountId"] == ACCOUNT_ID

    with mock_aws():
        async with _client(region="us-east-1") as client:
            with pytest.raises(ClientError) as err:  # pragma: no branch
                await client.get_repository(repositoryName=repository_name)

    ex = err.value
    assert ex.operation_name == "GetRepository"
    assert ex.response["ResponseMetadata"]["HTTPStatusCode"] == 400
    assert ex.response["Error"]["Code"] == "RepositoryDoesNotExistException"
    assert ex.response["Error"]["Message"] == f"{repository_name} does not exist"


@pytest.mark.asyncio
async def test_get_repository_invalid_repository_name_async() -> None:
    with mock_aws():
        async with _client() as client:
            with pytest.raises(ClientError) as err:  # pragma: no branch
                await client.get_repository(repositoryName="repository_one-@#@")

    ex = err.value
    assert ex.response["ResponseMetadata"]["HTTPStatusCode"] == 400
    assert ex.response["Error"]["Code"] == "InvalidRepositoryNameException"
    assert ex.response["Error"]["Message"] == INVALID_NAME_MESSAGE


@pytest.mark.asyncio
async def test_delete_repository_async() -> None:
    with mock_aws():
        async with _client(region="us-east-1") as client:
            response = await client.create_repository(repositoryName="repository_one")

            repository_id_create = response["repositoryMetadata"]["repositoryId"]

            delete_response = await client.delete_repository(
                repositoryName="repository_one"
            )

            assert delete_response.get("repositoryId") is not None
            assert repository_id_create == delete_response.get("repositoryId")

            final_response = await client.delete_repository(
                repositoryName="unknown_repository"
            )

    assert final_response.get("repositoryId") is None


@pytest.mark.asyncio
async def test_delete_repository_invalid_repository_name_async() -> None:
    with mock_aws():
        async with _client(region="us-east-1") as client:
            with pytest.raises(ClientError) as err:  # pragma: no branch
                await client.delete_repository(repositoryName="_rep@ository_one")

    ex = err.value
    assert ex.operation_name == "DeleteRepository"
    assert ex.response["ResponseMetadata"]["HTTPStatusCode"] == 400
    assert ex.response["Error"]["Code"] == "InvalidRepositoryNameException"
    assert ex.response["Error"]["Message"] == INVALID_NAME_MESSAGE
