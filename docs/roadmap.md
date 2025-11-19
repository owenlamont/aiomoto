# aiomoto Research Notes — Moto & aiobotocore

Last updated: 2025-11-17

## Project Goal Refresher

- Build `aiomoto`, an in-process adaptor that lets `aiobotocore`/`aioboto3`
  interact with Moto backends without running `moto_server`.
- Support both sync (`boto3`/`botocore`) and async (`aiobotocore`/`aioboto3`)
  clients in the same Moto state so resources stay consistent.
- Prioritise S3 and DynamoDB in early milestones.
- Enforce "aiomoto contexts only" for async-aware tests to avoid state splits
  between raw Moto decorators and the adapter.

---

## How Moto Works (key internals to leverage)

### Mock lifecycle & global wiring

- `moto.core.decorator.mock_aws` instantiates `MockAWS` (or proxy/server
  variants) based on settings.
- `MockAWS` manages `_nested_count` and `_mocks_active` so patching happens
  exactly once per outermost context.
- `_enable_patching` registers `BotocoreStubber` with `responses` so requests
  are intercepted before `botocore` touches the network.
- Moto pre-populates `botocore.handlers.BUILTIN_HANDLERS` with the stubber, so
  every boto3 client shares it when created after mocks start.
- Backends are global singletons stored in `moto.core.base_backend.BackendDict`,
  giving natural state sharing between sync and async code.

### Service-specific highlights

- **S3**: `S3Backend` keeps `buckets` with `FakeKey` objects backed by
  spool files. Operations are synchronous but thread safe enough for typical
  tests if we respect builtin locks.
- **DynamoDB**: `DynamoDBBackend` keeps ordered dicts for tables, backups, and
  streams. Expression parsing lives in helper modules, so the adapter mainly
  needs to forward requests correctly.

### Takeaways for aiomoto

1. Moto returns synchronous `botocore.awsrequest.AWSResponse` objects, so
   aiomoto must wrap them in `aiobotocore.awsrequest.AioAWSResponse` (or
   equivalent) before async code awaits `.content`.
2. Reuse Moto's existing contexts instead of re-implementing service mocks.
3. Ensure no HTTP calls occur. Every aiobotocore request should be handled by
   Moto's stubber via `before-send` events.

---

## How aiobotocore Processes Requests

1. `AioEndpoint._do_get_response` fires `before-send` events. When no handler
   returns a response it falls back to `_send`, which issues a real HTTP call.
2. `convert_to_response_dict` awaits `http_response.content`, so adapters must
   hand back awaitable responses.
3. Streaming outputs rely on `StreamingBody` wrappers over the raw response
   object.

### Hook points for aiomoto

- Register Moto's `botocore_stubber` on aiobotocore's hierarchical emitter so
  the `before-send` hook triggers in async clients.
- Patch `convert_to_response_dict` (or wrap responses earlier) so synchronous
  Moto responses behave like `AioAWSResponse` instances.
- Provide an async-friendly wrapper around Moto's `MockRawResponse` so
  streaming bodies can be read chunk by chunk.

---

## Proposed Architecture (summary)

1. **Context manager**: expose `mock_aws()` that works for both `with` and
   `async with`, internally wrapping Moto's own context and tracking nested
   enters.
2. **Patch module**: apply patches when the context starts (stubber
   registration, response adapters, HTTP guardrails) and remove them on exit.
3. **Version gate**: pin Moto + aiobotocore versions and document a
   compatibility table for each aiomoto release.

---

## Vertical Task Backlog (end-to-end slices)

Each task ports a narrow slice of Moto's test suite and wires every layer
(context manager, patching, tests) required for that slice to pass.

### Task V1 – S3 bucket smoke test (bootstrap)

- **Moto reference**: `tests/test_s3/test_s3.py::test_my_model_save` and
    `::test_key_save_to_missing_bucket`.
- **Goal**: prove `aiomoto.mock_aws()` lets async aiobotocore clients create and
    list a bucket while sharing state with sync boto3.
- **Work**:
  1. Implement `_MotoAsyncContext` exposed as `mock_aws()` for sync + async
     usage.
  2. Add `AioBotocorePatcher` that registers Moto's stubber and wraps
     `AWSResponse` objects.
  3. Guard against fallbacks to `_send` by raising if a real HTTP request is
     attempted.
  4. Port the Moto bucket tests to `tests/test_s3_async.py`, including the
     negative `NoSuchBucket` case.

### Task V2 – S3 object IO + streaming bodies

- **Moto reference**: `tests/test_s3/test_s3.py::test_empty_key` and
    `::test_empty_key_set_on_existing_key`.
- **Goal**: validate async `put_object`/`get_object` flows, including content
    length tracking and overwrites.
- **Work**:
  1. Extend the response wrapper to expose async streaming reads.
  2. Add async tests for empty payloads, rewrites, and metadata checks.
  3. Verify sync boto3 reads objects created by async clients.

### Task V3 – S3 list/prefix behaviour

- **Moto reference**: `tests/test_s3/test_s3.py::test_key_name_encoding_in_listing`.
- **Goal**: ensure async list operations (including `Delimiter`, `EncodingType`
    params) work through aiomoto.
- **Work**:
  1. Confirm response headers are preserved so aiobotocore parsers behave.
  2. Port the key-encoding test using async list operations.

### Task V4 – DynamoDB table + CRUD smoke

- **Moto reference**: `tests/test_dynamodb/test_dynamodb.py::test_create_table`
    and `::test_put_get_item`.
- **Goal**: create `tests/test_dynamodb_async.py` covering table creation,
    describe, and put/get operations that share state with boto3.
- **Work**:
  1. Ensure DynamoDB routing within the context handles regional backends.
  2. Port create-table and CRUD tests, including error propagation for missing
     tables.

### Task V5 – aioboto3 resource coverage

- **Moto reference**: reuse V1–V3 scenarios via `aioboto3.Session().resource("s3")`.
- **Goal**: prove aioboto3 resource APIs inherit the adapter behaviour.
- **Work**:
  1. Add a fixture that creates an aioboto3 session inside `mock_aws()`.
  2. Port bucket/object smoke tests using resource-style calls.

### Task V6 – Compatibility tooling

- Document version triplets in the README and enforce them at import time with
  friendly errors.

---

## Issue Draft – V1: S3 bucket smoke

### Title

Bootstrap aiomoto with S3 bucket smoke test

### Why

This proves the context manager plus aiobotocore patching stack works
end-to-end for the simplest S3 workflow and sets the testing pattern for later
slices.

### Acceptance Criteria

1. `aiomoto.mock_aws()` supports sync + async usage, wrapping Moto's context and
   applying patches once per outermost enter.
2. `AioBotocorePatcher` registers Moto's stubber and wraps Moto `AWSResponse`
   objects so `convert_to_response_dict` can await them.
3. `tests/test_s3_async.py` demonstrates:
   - A bucket created with boto3 is visible to aiobotocore and vice versa.
   - Accessing a non-existent bucket raises `ClientError` with `NoSuchBucket`.
4. Tests fail if any HTTP request is attempted while mocks are active.

### Implementation Notes

- Reference Moto tests in `tests/test_s3/test_s3.py` for expected behaviour.
- The response wrapper can be a thin adapter around Moto's `MockRawResponse`
  that provides async `read()` and iteration helpers.
- Document the "no mixing" rule in the README once the API exists.

---

## Open Questions / Follow-ups

- **Moto internals stability**: confirm maintainers consider `botocore_stubber`
  usage stable enough or whether aiomoto should vendor key bits.
- **Thread safety**: Moto is lightly tested for concurrent writes. Provide
  guidance for users who run many async tasks simultaneously.
- **Reset granularity**: explore exposing helper utilities that reset a single
  service backend without tearing down the entire context.
- **Error surface**: decide how to detect and warn when users try to mix raw
  Moto decorators with aiomoto contexts.

---

These notes will evolve as we prototype the context manager and
aiobotocore patches. Next step: implement Task V1 and turn the draft issue into
an actual GitHub issue once reviewed.
