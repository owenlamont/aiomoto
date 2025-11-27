from __future__ import annotations

from typing import Any, TYPE_CHECKING

import aioboto3
import pytest

from aiomoto import mock_aws


if TYPE_CHECKING:
    from aioboto3.client import ClientCreatorContext


def _client() -> ClientCreatorContext[Any]:
    return aioboto3.Session().client("support", region_name="us-east-1")


@pytest.mark.asyncio
async def test_describe_trusted_advisor_checks_count() -> None:
    with mock_aws():
        async with _client() as client:
            response = await client.describe_trusted_advisor_checks(language="en")

    assert len(response["checks"]) == 104


@pytest.mark.asyncio
async def test_describe_trusted_advisor_checks_contains_expected_id() -> None:
    with mock_aws():
        async with _client() as client:
            response = await client.describe_trusted_advisor_checks(language="en")

    check_ids = [check["id"] for check in response["checks"]]
    assert "zXCkfM1nI3" in check_ids


@pytest.mark.asyncio
async def test_describe_trusted_advisor_checks_contains_expected_name() -> None:
    with mock_aws():
        async with _client() as client:
            response = await client.describe_trusted_advisor_checks(language="en")

    check_names = [check["name"] for check in response["checks"]]
    assert "Unassociated Elastic IP Addresses" in check_names


@pytest.mark.asyncio
async def test_refresh_trusted_advisor_check_returns_check_id() -> None:
    with mock_aws():
        async with _client() as client:
            check_name = "XXXIIIY"
            response = await client.refresh_trusted_advisor_check(checkId=check_name)

    assert response["status"]["checkId"] == check_name


@pytest.mark.asyncio
async def test_refresh_trusted_advisor_check_returns_status() -> None:
    possible_statuses = ["none", "enqueued", "processing", "success", "abandoned"]
    with mock_aws():
        async with _client() as client:
            check_name = "XXXIIIY"
            response = await client.refresh_trusted_advisor_check(checkId=check_name)

    assert response["status"]["status"] in possible_statuses


@pytest.mark.parametrize(
    "possible_statuses",
    [
        ["none", "enqueued", "processing"],
        ["none", "enqueued", "processing", "success", "abandoned"],
    ],
)
@pytest.mark.asyncio
async def test_refresh_trusted_advisor_check_cycles(
    possible_statuses: list[str],
) -> None:
    with mock_aws():
        async with _client() as client:
            check_name = "XXXIIIY"
            actual_statuses = []
            for _ in possible_statuses:
                response = await client.refresh_trusted_advisor_check(
                    checkId=check_name
                )
                actual_statuses.append(response["status"]["status"])

    assert actual_statuses == possible_statuses


@pytest.mark.asyncio
async def test_refresh_trusted_advisor_check_cycles_independent() -> None:
    possible_statuses = ["none", "enqueued", "processing", "success", "abandoned"]
    with mock_aws():
        async with _client() as client:
            check_1 = "XXXIIIY"
            check_2 = "XXXIIIZ"
            check_1_statuses = []
            check_2_statuses = []
            for _ in possible_statuses:
                response = await client.refresh_trusted_advisor_check(checkId=check_1)
                check_1_statuses.append(response["status"]["status"])
            for _ in possible_statuses:
                response = await client.refresh_trusted_advisor_check(checkId=check_2)
                check_2_statuses.append(response["status"]["status"])

    assert check_1_statuses == possible_statuses
    assert check_2_statuses == possible_statuses


@pytest.mark.asyncio
async def test_refresh_trusted_advisor_check_cycle_wraps() -> None:
    possible_statuses = ["none", "enqueued", "processing", "success", "abandoned"]
    with mock_aws():
        async with _client() as client:
            check_name = "XXXIIIY"
            for _ in possible_statuses:
                await client.refresh_trusted_advisor_check(checkId=check_name)
            expected_none_response = await client.refresh_trusted_advisor_check(
                checkId=check_name
            )

    assert expected_none_response["status"]["status"] == "none"


@pytest.mark.asyncio
async def test_support_case_resolve() -> None:
    with mock_aws():
        async with _client() as client:
            create_case_response = await client.create_case(
                subject="test_subject",
                serviceCode="test_service_code",
                severityCode="low",
                categoryCode="test_category_code",
                communicationBody="test_communication_body",
                ccEmailAddresses=["test_email_cc"],
                language="test_language",
                issueType="test_issue_type",
                attachmentSetId="test_attachment_set_id",
            )
            case_id = create_case_response["caseId"]

            resolve_case_response = await client.resolve_case(caseId=case_id)

    possible_case_status = [
        "opened",
        "pending-customer-action",
        "reopened",
        "unassigned",
        "resolved",
        "work-in-progress",
    ]
    assert resolve_case_response["initialCaseStatus"] in possible_case_status
    assert resolve_case_response["finalCaseStatus"] == "resolved"
