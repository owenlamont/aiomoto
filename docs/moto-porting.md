# Moto Test Porting Plan (tracking)

<!-- markdownlint-disable MD013 -->

Goal: broaden service coverage in `aiomoto` by porting lightweight moto tests (self‑contained Python modules or fixtures inside the repo) to async clients (`aioboto3` / `aiobotocore`) while mirroring moto’s test layout. Prioritise incremental, stoppable steps; skip tests that rely on external data files outside the Python modules.

## Current async coverage in `aiomoto`

- `s3`, `dynamodb`, `secretsmanager`, `ses` plus basic smoke/context tests (`tests/test_s3_async.py`, `test_dynamodb_async.py`, `test_secretsmanager_async.py`, `test_ses_async.py`, `test_smoke.py`, `test_mock_decorator.py`, `test_context_internal.py`, `test_s3fs_integration.py`).
- No async coverage yet for most other AWS services.

### Survey of moto test modules (top level `moto/tests`)

- Moto has ~110 service directories; most have only Python tests and no extra data files.
- Modules containing non‑Python data files (de‑prioritise or adapt inline): `test_acm` (cert/key fixtures), `test_apigateway` (YAML/JSON API specs), `test_awslambda` (zip layer fixture), `test_core` (protocol output JSONs), `test_elastictranscoder` (data dir), `test_glacier` (gz payload), `test_ssm` (YAML template), `test_stepfunctions` (multiple JSON templates).
- All other modules are purely Python and generally self‑contained.

### Porting approach

- **Structure:** create matching module names under `tests/` (e.g., `tests/test_ec2_async.py`) to stay parallel with moto; port at the module level when small/clean, otherwise cherry‑pick self‑contained test functions.
- **Async client choice:** favour `aioboto3.Session().client/resource` where moto tests use high‑level boto3 APIs; fall back to `aiobotocore.AioSession` when minimal changes from synchronous client semantics are needed. Stay consistent within a module.
- **Mocking:** wrap tests with `aiomoto.mock_aws()` (or service‑specific decorators) mirroring moto’s usage; avoid external services/files.
- **Skips & notes:** if a test needs external data files or exposes an `aiomoto` gap/bug, mark it `pytest.mark.skip` with a short reason and record it below.
- **Incremental cadence:** port a small module at a time; pause after each module so changes can be committed before continuing.

### Candidate ordering (low effort first)

- Very small, data‑free modules (1–3 test files): `test_codebuild`, `test_codecommit`, `test_codedeploy`, `test_codepipeline`, `test_elastictranscoder` (needs inspection for data dir), `test_kafka`, `test_meteringmarketplace`, `test_memorydb`, `test_networkfirewall`, `test_opensearchserverless`, `test_panorama`, `test_personalize`, `test_pipes`, `test_ram`, `test_rdsdata`, `test_resiliencehub`, `test_securityhub`, `test_servicequotas`, `test_shield`, `test_timestreamquery`, `test_ivs`, etc.
- Medium, clean modules to follow: `test_ec2`, `test_sqs`, `test_sns`, `test_sts`, `test_events`, `test_kms`, `test_iam`, `test_logs`, `test_autoscaling`, `test_rds`, `test_redshift`, `test_glue`, `test_cloudwatch`.
- Data‑dependent modules (consider later with inline data or re‑encoding fixtures): `test_apigateway`, `test_stepfunctions`, `test_acm`, `test_awslambda`, `test_core`, `test_glacier`, `test_ssm`, `test_elastictranscoder`.

### Tracking table (all moto test modules)

- Priority buckets: `low` (≤3 py files, no data), `medium` (4–10 py files), `large` (>10 py files), `data-heavy` (any extra data files).
- Status to fill as we go: `pending`, `planned`, `ported`, `partial`, `skipped`, `issue-found` (with short note).

| Module | Py files | Data files | Priority | Status | Notes |
| --- | --- | --- | --- | --- | --- |
| test_sts | 4 | 0 | medium | ported | popularity-first queue |
| test_kms | 10 | 0 | medium | partial | popularity-first queue |
| test_sqs | 6 | 0 | medium | ported | popularity-first queue |
| test_sns | 10 | 0 | medium | partial | popularity-first queue |
| test_events | 9 | 0 | medium | partial | popularity-first queue |
| test_dynamodb_v20111205 | 3 | 0 | low | ported | popularity-first queue |
| test_rdsdata | 2 | 0 | low | pending | skipped: requires motoapi server; not ported |
| test_logs | 12 | 0 | large | pending | skip for now: many server-mode/delivery interactions; needs offline plan |
| test_ec2 | 52 | 0 | large | planned | popularity-first queue |
| test_autoscaling | 15 | 0 | large | planned | popularity-first queue |
| test_apigatewayv2 | 14 | 0 | large | planned | popularity-first queue |
| test_sesv2 | 3 | 0 | low | planned | popularity-first queue |
| test_s3control | 6 | 0 | medium | planned | popularity-first queue |
| test_s3tables | 3 | 0 | low | planned | popularity-first queue |
| test_s3vectors | 3 | 0 | low | planned | popularity-first queue |
| test_redshift | 4 | 0 | medium | planned | popularity-first queue |
| test_redshiftdata | 4 | 0 | medium | planned | popularity-first queue |
| test_kinesis | 10 | 0 | medium | planned | popularity-first queue |
| test_cloudwatch | 8 | 0 | medium | planned | popularity-first queue |
| test_iam | 14 | 0 | large | planned | popularity-first queue |
| test_secretsmanager | 7 | 0 | medium | exists | exists (aiomoto async coverage present) |
| test_ses | 6 | 0 | medium | exists | exists (aiomoto async coverage present) |
| test_dynamodb | 34 | 0 | large | exists | aiomoto has async coverage; not a moto port |
| test_s3 | 36 | 0 | large | exists | exists (aiomoto async coverage present) |
| test_acmpca | 2 | 0 | low | pending |  |
| test_apigatewaymanagementapi | 2 | 0 | low | pending |  |
| test_appmesh | 3 | 0 | low | ported |  |
| test_awslambda_simple | 2 | 0 | low | ported | async simple invoke ported |
| test_backup | 2 | 0 | low | pending |  |
| test_bedrock | 2 | 0 | low | pending |  |
| test_bedrockagent | 2 | 0 | low | pending |  |
| test_clouddirectory | 3 | 0 | low | ported | requires moto DEFAULT_ACCOUNT_ID ARN formatting |
| test_cloudhsmv2 | 2 | 0 | low | pending |  |
| test_codebuild | 1 | 0 | low | ported | good first port |
| test_codecommit | 1 | 0 | low | ported | good first port |
| test_codedeploy | 2 | 0 | low | ported | async app/group/deployment/list/batch coverage |
| test_codepipeline | 2 | 0 | low | ported | async create/update/list/tag pipelines |
| test_cognitoidentity | 3 | 0 | low | ported | basic pool CRUD |
| test_connectcampaigns | 2 | 0 | low | pending |  |
| test_datasync | 2 | 0 | low | ported |  |
| test_dax | 3 | 0 | low | ported |  |
| test_directconnect | 3 | 0 | low | ported |  |
| test_dsql | 2 | 0 | low | pending |  |
| test_dynamodbstreams | 2 | 0 | low | pending |  |
| test_ebs | 2 | 0 | low | pending |  |
| test_ec2instanceconnect | 1 | 0 | low | pending |  |
| test_elasticache | 3 | 0 | low | ported |  |
| test_elasticbeanstalk | 3 | 0 | low | ported | moto nests Application info under Application key |
| test_emrcontainers | 3 | 0 | low | ported | delete leaves cluster in TERMINATED; describe still works |
| test_emrserverless | 3 | 0 | low | ported | type must be SPARK; delete returns TERMINATED state |
| test_forecast | 2 | 0 | low | pending |  |
| test_fsx | 3 | 0 | low | ported |  |
| test_identitystore | 2 | 0 | low | ported |  |
| test_iotdata | 3 | 0 | low | ported | create IoT thing first; payload reads are async |
| test_ivs | 2 | 0 | low | ported |  |
| test_kafka | 2 | 0 | low | ported | async cluster v2/provisioned/tag/delete |
| test_kinesisanalyticsv2 | 3 | 0 | low | skipped | DeleteApplication not implemented; create requires ServiceExecutionRole |
| test_kinesisvideo | 3 | 0 | low | ported | create_stream returns StreamARN; list_streams has StreamName |
| test_kinesisvideoarchivedmedia | 3 | 0 | low | skipped | ListFragments raises NotYetImplemented (404) in moto |
| test_lexv2models | 2 | 0 | low | pending |  |
| test_macie | 2 | 0 | low | pending |  |
| test_mediaconnect | 3 | 0 | low | ported | flow create/list/describe/delete/start/stop |
| test_medialive | 3 | 0 | low | ported | pagination inside mock context |
| test_mediapackage | 3 | 0 | low | ported | channel + origin endpoint CRUD |
| test_mediapackagev2 | 3 | 0 | low | ported | channel group list/delete; conflict delete path |
| test_mediastore | 3 | 0 | low | ported |  |
| test_mediastoredata | 3 | 0 | low | ported |  |
| test_memorydb | 2 | 0 | low | ported | async cluster/subnet/snapshot/describe |
| test_meteringmarketplace | 1 | 0 | low | ported | good first port |
| test_networkfirewall | 2 | 0 | low | ported | good first port |
| test_networkmanager | 3 | 0 | low | ported | global/core network CRUD + tagging |
| test_opensearch | 3 | 0 | low | pending |  |
| test_opensearchserverless | 2 | 0 | low | pending | good first port |
| test_organizations | 3 | 0 | low | pending |  |
| test_osis | 3 | 0 | low | ported | minimal pipeline create/list/delete; VpcOptions skipped (moto validation) |
| test_personalize | 2 | 0 | low | pending |  |
| test_pipes | 2 | 0 | low | skipped | create/list pipe not implemented in moto; tests assert 404 |
| test_polly | 3 | 0 | low | ported |  |
| test_ram | 2 | 0 | low | pending |  |
| test_rekognition | 2 | 0 | low | pending |  |
| test_resourcegroups | 2 | 0 | low | pending |  |
| test_route53domains | 2 | 0 | low | pending |  |
| test_s3bucket_path | 3 | 0 | low | pending |  |
| test_sagemakermetrics | 3 | 0 | low | pending |  |
| test_sagemakerruntime | 2 | 0 | low | pending |  |
| test_securityhub | 2 | 0 | low | pending | good first port |
| test_servicecatalog | 3 | 0 | low | pending |  |
| test_servicecatalogappregistry | 3 | 0 | low | pending |  |
| test_servicequotas | 2 | 0 | low | pending |  |
| test_shield | 2 | 0 | low | pending |  |
| test_signer | 3 | 0 | low | pending |  |
| test_special_cases | 1 | 0 | low | pending |  |
| test_support | 3 | 0 | low | ported | trusted advisor + case resolve |
| test_synthetics | 3 | 0 | low | pending |  |
| test_textract | 3 | 0 | low | pending |  |
| test_timestreaminfluxdb | 3 | 0 | low | pending |  |
| test_timestreamquery | 2 | 0 | low | pending | good first port |
| test_timestreamwrite | 5 | 0 | medium | ported | database CRUD/list/update error path |
| test_transcribe | 2 | 0 | low | pending |  |
| test_transfer | 2 | 0 | low | pending |  |
| test_vpclattice | 3 | 0 | low | pending |  |
| test_workspaces | 2 | 0 | low | pending |  |
| test_workspacesweb | 2 | 0 | low | pending |  |
| test_xray | 3 | 0 | low | pending |  |
| test_amp | 4 | 0 | medium | pending |  |
| test_appconfig | 4 | 0 | medium | pending |  |
| test_applicationautoscaling | 4 | 0 | medium | pending |  |
| test_appsync | 7 | 0 | medium | pending |  |
| test_athena | 7 | 0 | medium | pending |  |
| test_batch_simple | 4 | 0 | medium | pending |  |
| test_budgets | 4 | 0 | medium | pending |  |
| test_ce | 4 | 0 | medium | pending |  |
| test_cloudfront | 9 | 0 | medium | pending |  |
| test_cloudtrail | 5 | 0 | medium | pending |  |
| test_cognitoidp | 5 | 0 | medium | pending |  |
| test_comprehend | 4 | 0 | medium | pending |  |
| test_config | 5 | 0 | medium | pending |  |
| test_databrew | 5 | 0 | medium | pending |  |
| test_datapipeline | 4 | 0 | medium | pending |  |
| test_dms | 4 | 0 | medium | pending |  |
| test_ds | 6 | 0 | medium | pending |  |
| test_ecr | 7 | 0 | medium | pending |  |
| test_ecs | 10 | 0 | medium | pending |  |
| test_eks | 6 | 0 | medium | pending |  |
| test_elb | 7 | 0 | medium | pending |  |
| test_emr | 8 | 0 | medium | pending |  |
| test_es | 4 | 0 | medium | pending |  |
| test_firehose | 7 | 0 | medium | pending |  |
| test_greengrass | 8 | 0 | medium | pending |  |
| test_guardduty | 5 | 0 | medium | pending |  |
| test_inspector2 | 8 | 0 | medium | pending |  |
| test_lakeformation | 4 | 0 | medium | pending |  |
| test_managedblockchain | 8 | 0 | medium | pending |  |
| test_mq | 6 | 0 | medium | pending |  |
| test_neptune | 5 | 0 | medium | pending |  |
| test_panorama | 5 | 0 | medium | pending |  |
| test_pinpoint | 4 | 0 | medium | pending |  |
| test_quicksight | 8 | 0 | medium | pending |  |
| test_resiliencehub | 4 | 0 | medium | pending |  |
| test_resourcegroupstaggingapi | 9 | 0 | medium | pending |  |
| test_route53 | 10 | 0 | medium | pending |  |
| test_route53resolver | 6 | 0 | medium | pending |  |
| test_scheduler | 5 | 0 | medium | pending |  |
| test_sdb | 4 | 0 | medium | pending |  |
| test_servicediscovery | 7 | 0 | medium | pending |  |
| test_ssoadmin | 6 | 0 | medium | pending |  |
| test_timestreamwrite | 5 | 0 | medium | pending |  |
| test_utilities | 6 | 0 | medium | pending |  |
| test_wafv2 | 10 | 0 | medium | pending |  |
| test_batch | 14 | 0 | large | pending |  |
| test_cloudformation | 29 | 0 | large | pending |  |
| test_efs | 12 | 0 | large | pending |  |
| test_elbv2 | 12 | 0 | large | pending |  |
| test_glue | 11 | 0 | large | pending |  |
| test_iot | 21 | 0 | large | pending |  |
| test_moto_api | 12 | 0 | large | pending |  |
| test_rds | 18 | 0 | large | pending |  |
| test_sagemaker | 27 | 0 | large | pending |  |
| test_swf | 21 | 0 | large | pending |  |
| test_acm | 3 | 8 | data-heavy | pending | cert/key fixtures; likely skip until needed |
| test_apigateway | 14 | 6 | data-heavy | pending | YAML/JSON API specs |
| test_awslambda | 14 | 1 | data-heavy | pending | zip layer fixture |
| test_core | 33 | 6 | data-heavy | pending | protocol JSON outputs |
| test_elastictranscoder | 2 | 1 | data-heavy | pending | data dir present |
| test_glacier | 5 | 1 | data-heavy | pending | gz payload |
| test_ssm | 16 | 1 | data-heavy | pending | YAML template |
| test_stepfunctions | 21 | 19 | data-heavy | pending | parser templates |

### Current strategy (branch state, pre-0.0.7 release)

- Goal is **shim-contract coverage**, not service-by-service parity. We keep a small
  set that exercises aiomoto’s patching, async pathways, and prevents real IO.
- **Kept test modules:** `test_mock_aws_context.py`, `test_mock_decorator.py`,
  `test_context_internal.py`, `patches/test_core_internal.py`, `test_s3fs_integration.py`,
  `test_lambda_simple_async.py`, `test_s3_async.py`, `test_dynamodb_async.py`,
  `test_sqs_async.py`, `test_sns_async.py`, `test_sts_async.py`, `test_kms_async.py`,
  `test_events_async.py`, `test_kafka_async.py`, `test_smoke.py`.
- **Removed:** the long tail of straight CRUD moto ports (most other `test_*_async.py`
  modules). Rationale: they mostly re-test moto, added ~8k LoC, and didn’t increase
  aiomoto source coverage. Re-introduce only if a service needs aiomoto-specific
  behavior or a regression guard.

### Tracking log

- Future additions should be explicitly justified (e.g., aiomoto behavior difference,
  async-only semantics, regression seen in moto drift). Update the table above with
  status `ported`/`skipped` plus a short reason when adding or dropping.
