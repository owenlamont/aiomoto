from __future__ import annotations

from typing import Any, TYPE_CHECKING

import aioboto3
from botocore.exceptions import ClientError
import pytest

from aiomoto import mock_aws


if TYPE_CHECKING:
    from aioboto3.client import ClientCreatorContext


def _client() -> ClientCreatorContext[Any]:
    return aioboto3.Session().client("backup", region_name="eu-west-1")


@pytest.mark.asyncio
async def test_create_backup_plan_async() -> None:
    with mock_aws():
        async with _client() as client:
            vault = await client.create_backup_vault(BackupVaultName="vault")
            resp = await client.create_backup_plan(
                BackupPlan={
                    "BackupPlanName": "plan",
                    "Rules": [
                        {
                            "RuleName": "rule",
                            "TargetBackupVaultName": vault["BackupVaultName"],
                        }
                    ],
                }
            )

    assert "BackupPlanId" in resp
    assert "VersionId" in resp


@pytest.mark.asyncio
async def test_create_backup_plan_already_exists_async() -> None:
    rules = [{"RuleName": "r1", "TargetBackupVaultName": "vault"}]
    with mock_aws():
        async with _client() as client:
            await client.create_backup_plan(
                BackupPlan={"BackupPlanName": "plan", "Rules": rules}
            )
            with pytest.raises(ClientError) as exc:
                await client.create_backup_plan(
                    BackupPlan={"BackupPlanName": "plan", "Rules": rules}
                )

    assert exc.value.response["Error"]["Code"] == "AlreadyExistsException"


@pytest.mark.asyncio
async def test_get_and_delete_backup_plan_async() -> None:
    with mock_aws():
        async with _client() as client:
            vault = await client.create_backup_vault(BackupVaultName="vault")
            plan = await client.create_backup_plan(
                BackupPlan={
                    "BackupPlanName": "plan",
                    "Rules": [
                        {
                            "RuleName": "rule1",
                            "TargetBackupVaultName": vault["BackupVaultName"],
                            "ScheduleExpression": "cron(0 1 ? * * *)",
                            "StartWindowMinutes": 60,
                            "CompletionWindowMinutes": 120,
                        },
                        {
                            "RuleName": "rule2",
                            "TargetBackupVaultName": vault["BackupVaultName"],
                        },
                    ],
                }
            )

            fetched = await client.get_backup_plan(BackupPlanId=plan["BackupPlanId"])
            deleted = await client.delete_backup_plan(BackupPlanId=plan["BackupPlanId"])

    assert len(fetched["BackupPlan"]["Rules"]) == 2
    assert "DeletionDate" in deleted


@pytest.mark.asyncio
async def test_get_backup_plan_invalid_ids_async() -> None:
    with mock_aws():
        async with _client() as client:
            with pytest.raises(ClientError) as exc:
                await client.get_backup_plan(BackupPlanId="missing")

    assert exc.value.response["Error"]["Code"] == "ResourceNotFoundException"
