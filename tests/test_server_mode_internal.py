from __future__ import annotations

import sys
from types import ModuleType

import pytest
from pytest_mock import MockerFixture

from aiomoto.patches.server_mode import (
    _apply_client_defaults,
    _default_creds,
    _default_region,
    _merge_path_style,
    _should_inject,
    AutoEndpointMode,
    ServerModePatcher,
)


def test_default_region_prefers_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AWS_REGION", raising=False)
    monkeypatch.delenv("AWS_DEFAULT_REGION", raising=False)
    assert _default_region() == "us-east-1"
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-west-2")
    assert _default_region() == "us-west-2"
    monkeypatch.setenv("AWS_REGION", "eu-west-1")
    assert _default_region() == "eu-west-1"


def test_default_creds_prefers_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "key")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "secret")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "token")
    assert _default_creds() == ("key", "secret", "token")


def test_should_inject_modes() -> None:
    assert _should_inject(AutoEndpointMode.DISABLED, None) is False
    assert _should_inject(AutoEndpointMode.FORCE, "http://x") is True
    assert _should_inject(AutoEndpointMode.IF_MISSING, None) is True
    assert _should_inject(AutoEndpointMode.IF_MISSING, "http://x") is False


def test_merge_path_style_with_and_without_merge() -> None:
    class _Config:
        def merge(self, other: object) -> str:
            return f"merged:{other}"

    merged = _merge_path_style(_Config())
    assert isinstance(merged, str)
    existing = object()
    assert _merge_path_style(existing) is existing
    assert _merge_path_style(None) is not None


def test_apply_client_defaults_noop_when_disabled() -> None:
    args: dict[str, object] = {"endpoint_url": "http://example.com"}
    _apply_client_defaults(args, "http://server", AutoEndpointMode.DISABLED)
    assert args["endpoint_url"] == "http://example.com"


def test_apply_client_defaults_sets_region_and_creds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("AWS_REGION", raising=False)
    monkeypatch.delenv("AWS_DEFAULT_REGION", raising=False)
    monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)
    monkeypatch.setenv("AWS_SESSION_TOKEN", "token")
    args: dict[str, object] = {}
    _apply_client_defaults(args, "http://server", AutoEndpointMode.FORCE)
    assert args["endpoint_url"] == "http://server"
    assert args["use_ssl"] is False
    assert args["region_name"] == "us-east-1"
    assert args["aws_access_key_id"] == "test"
    assert args["aws_secret_access_key"] == "test"  # noqa: S105
    assert args["aws_session_token"] == "token"  # noqa: S105
    assert args["config"] is not None


def test_apply_client_defaults_skips_session_token_when_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("AWS_SESSION_TOKEN", raising=False)
    args: dict[str, object] = {}
    _apply_client_defaults(args, "http://server", AutoEndpointMode.FORCE)
    assert "aws_session_token" not in args


def test_apply_client_defaults_respects_existing_creds() -> None:
    args: dict[str, object] = {
        "aws_access_key_id": "existing",
        "aws_secret_access_key": "secret",
        "region_name": "us-west-1",
    }
    _apply_client_defaults(args, "http://server", AutoEndpointMode.FORCE)
    assert args["aws_access_key_id"] == "existing"
    assert args["region_name"] == "us-west-1"


def test_patcher_stop_noop_when_zero() -> None:
    patcher = ServerModePatcher()
    patcher.stop()


def test_patch_botocore_double_call() -> None:
    patcher = ServerModePatcher()
    patcher._patch_botocore()
    patcher._patch_botocore()
    patcher._restore_botocore()


def test_patched_botocore_requires_config() -> None:
    patcher = ServerModePatcher()
    patcher._patch_botocore()
    from botocore.session import Session as BotocoreSession

    with pytest.raises(RuntimeError, match="auto-endpoint not configured"):
        BotocoreSession().create_client("s3")
    patcher._restore_botocore()


def test_restore_botocore_noop_when_missing() -> None:
    patcher = ServerModePatcher()
    patcher._restore_botocore()


def test_patch_aiobotocore_skips_when_missing(mocker: MockerFixture) -> None:
    patcher = ServerModePatcher()
    mocker.patch(
        "aiomoto.patches.server_mode.importlib.util.find_spec", return_value=None
    )
    patcher._patch_aiobotocore()
    assert patcher._original_aio_create is None


def test_patch_aiobotocore_noop_when_already_patched() -> None:
    patcher = ServerModePatcher()
    patcher._original_aio_create = lambda *args, **kwargs: None
    patcher._patch_aiobotocore()


@pytest.mark.asyncio
async def test_aiobotocore_patched_requires_config() -> None:
    from aiobotocore.session import AioSession

    patcher = ServerModePatcher()
    patcher._patch_aiobotocore()
    method_name = "_create_client"
    create_client = getattr(AioSession(), method_name)
    with pytest.raises(RuntimeError, match="auto-endpoint not configured"):
        await create_client("s3")
    patcher._restore_aiobotocore()


def test_restore_aiobotocore_noop_when_missing() -> None:
    patcher = ServerModePatcher()
    patcher._restore_aiobotocore()


def test_patch_s3fs_skips_when_missing(mocker: MockerFixture) -> None:
    patcher = ServerModePatcher()
    mocker.patch(
        "aiomoto.patches.server_mode.importlib.util.find_spec", return_value=None
    )
    patcher._patch_s3fs()
    assert patcher._original_s3fs_init is None


def test_patch_s3fs_noop_when_already_patched() -> None:
    patcher = ServerModePatcher()
    patcher._original_s3fs_init = lambda *args, **kwargs: None
    patcher._patch_s3fs()


def test_restore_s3fs_noop_when_missing() -> None:
    patcher = ServerModePatcher()
    patcher._restore_s3fs()


def test_patch_s3fs_injects_defaults(
    monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture
) -> None:
    class _S3FileSystem:  # noqa: B903
        def __init__(
            self,
            *,
            endpoint_url: str | None = None,
            client_kwargs: dict[str, object] | None = None,
            config_kwargs: dict[str, object] | None = None,
            use_ssl: bool | None = None,
        ) -> None:
            self.endpoint_url = endpoint_url
            self.client_kwargs = client_kwargs
            self.config_kwargs = config_kwargs
            self.use_ssl = use_ssl

    s3fs_module = ModuleType("s3fs")
    s3fs_core = ModuleType("s3fs.core")
    attr_name = "S3FileSystem"
    setattr(s3fs_core, attr_name, _S3FileSystem)
    monkeypatch.setitem(sys.modules, "s3fs", s3fs_module)
    monkeypatch.setitem(sys.modules, "s3fs.core", s3fs_core)
    mocker.patch(
        "aiomoto.patches.server_mode.importlib.util.find_spec", return_value=object()
    )

    patcher = ServerModePatcher()
    patcher._endpoint = "http://localhost:5000"
    patcher._mode = AutoEndpointMode.FORCE
    patcher._patch_s3fs()
    fs = s3fs_core.S3FileSystem()
    assert fs.endpoint_url == "http://localhost:5000"
    assert fs.use_ssl is False
    assert fs.client_kwargs is not None
    assert fs.config_kwargs == {"s3": {"addressing_style": "path"}}
    patcher._restore_s3fs()


def test_patch_s3fs_does_not_override_user_kwargs(
    monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture
) -> None:
    class _S3FileSystem:  # noqa: B903
        def __init__(
            self,
            *,
            endpoint_url: str | None = None,
            client_kwargs: dict[str, object] | None = None,
            config_kwargs: dict[str, object] | None = None,
            use_ssl: bool | None = None,
        ) -> None:
            self.endpoint_url = endpoint_url
            self.client_kwargs = client_kwargs
            self.config_kwargs = config_kwargs
            self.use_ssl = use_ssl

    s3fs_module = ModuleType("s3fs")
    s3fs_core = ModuleType("s3fs.core")
    attr_name = "S3FileSystem"
    setattr(s3fs_core, attr_name, _S3FileSystem)
    monkeypatch.setitem(sys.modules, "s3fs", s3fs_module)
    monkeypatch.setitem(sys.modules, "s3fs.core", s3fs_core)
    mocker.patch(
        "aiomoto.patches.server_mode.importlib.util.find_spec", return_value=object()
    )

    patcher = ServerModePatcher()
    patcher._endpoint = "http://localhost:5000"
    patcher._mode = AutoEndpointMode.FORCE
    patcher._patch_s3fs()
    fs = s3fs_core.S3FileSystem(client_kwargs={"region_name": "us-east-1"})
    assert fs.client_kwargs == {"region_name": "us-east-1"}
    patcher._restore_s3fs()
