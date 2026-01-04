from __future__ import annotations

import sys
import sysconfig
from types import ModuleType

import pytest
from pytest_mock import MockerFixture

from aiomoto.patches.server_mode import (
    _apply_client_defaults,
    _apply_pandas_storage_options,
    _apply_polars_fsspec_storage_options,
    _apply_polars_storage_options,
    _default_creds,
    _default_region,
    _is_s3_source,
    _is_s3_url,
    _merge_path_style,
    _pandas_client_kwargs,
    _pandas_modules,
    _polars_fsspec_has_endpoint,
    _polars_modules,
    _polars_storage_options_has_endpoint,
    _require_server_settings,
    _should_inject,
    _storage_options_has_endpoint,
    _wrap_pandas_get_filepath,
    _wrap_pandas_get_path,
    _wrap_polars_write_ndjson,
    AutoEndpointMode,
    ServerModePatcher,
)


def _skip_if_free_threaded() -> None:
    if sysconfig.get_config_var("Py_GIL_DISABLED"):
        pytest.skip("pandas patching disabled on free-threaded builds")


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


def test_is_s3_url_rejects_non_str() -> None:
    assert _is_s3_url(123) is False


def test_is_s3_url_accepts_s3_like() -> None:
    assert _is_s3_url("s3://bucket/key") is True


def test_is_s3_source_handles_sequences() -> None:
    assert _is_s3_source(["s3://bucket/key"]) is True
    assert _is_s3_source(["local/file"]) is False


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


def test_pandas_client_kwargs_defaults_to_empty() -> None:
    assert _pandas_client_kwargs({}) == {}


def test_pandas_client_kwargs_returns_none_on_invalid() -> None:
    assert _pandas_client_kwargs({"client_kwargs": "bad"}) is None


def test_storage_options_has_endpoint_detects_top_level() -> None:
    assert _storage_options_has_endpoint({"endpoint_url": "http://example.com"})


def test_storage_options_has_endpoint_detects_client_kwargs() -> None:
    assert _storage_options_has_endpoint(
        {"client_kwargs": {"endpoint_url": "http://example.com"}}
    )


def test_storage_options_has_endpoint_false_when_missing() -> None:
    assert not _storage_options_has_endpoint({"anon": False})


def test_storage_options_has_endpoint_true_on_invalid_client_kwargs() -> None:
    assert _storage_options_has_endpoint({"client_kwargs": "bad"})


def test_apply_pandas_storage_options_respects_if_missing() -> None:
    storage_options = {"client_kwargs": {"endpoint_url": "http://example.com"}}
    result = _apply_pandas_storage_options(
        storage_options, "http://server", AutoEndpointMode.IF_MISSING
    )
    assert result is storage_options


def test_apply_pandas_storage_options_respects_if_missing_top_level_endpoint() -> None:
    storage_options = {"endpoint_url": "http://example.com"}
    result = _apply_pandas_storage_options(
        storage_options, "http://server", AutoEndpointMode.IF_MISSING
    )
    assert result is storage_options


def test_apply_pandas_storage_options_injects_when_if_missing_without_endpoint() -> (
    None
):
    storage_options = {"anon": False}
    result = _apply_pandas_storage_options(
        storage_options, "http://server", AutoEndpointMode.IF_MISSING
    )
    assert result is not None
    assert result is not storage_options
    assert result["endpoint_url"] == "http://server"
    assert result["client_kwargs"]["endpoint_url"] == "http://server"


def test_apply_pandas_storage_options_if_missing_ignores_bad_client_kwargs() -> None:
    storage_options = {"client_kwargs": "bad"}
    result = _apply_pandas_storage_options(
        storage_options, "http://server", AutoEndpointMode.IF_MISSING
    )
    assert result is storage_options


def test_apply_pandas_storage_options_injects_endpoint() -> None:
    result = _apply_pandas_storage_options(
        None, "http://server", AutoEndpointMode.FORCE
    )
    assert result is not None
    assert result["endpoint_url"] == "http://server"
    assert result["use_ssl"] is False
    client_kwargs = result["client_kwargs"]
    assert client_kwargs["endpoint_url"] == "http://server"
    assert client_kwargs["region_name"] == "us-east-1"


def test_apply_pandas_storage_options_noop_when_disabled() -> None:
    storage_options = {"client_kwargs": {"endpoint_url": "http://example.com"}}
    result = _apply_pandas_storage_options(
        storage_options, "http://server", AutoEndpointMode.DISABLED
    )
    assert result is storage_options


def test_apply_pandas_storage_options_ignores_bad_client_kwargs() -> None:
    storage_options = {"client_kwargs": "bad"}
    result = _apply_pandas_storage_options(
        storage_options, "http://server", AutoEndpointMode.FORCE
    )
    assert result is storage_options


def test_apply_pandas_storage_options_preserves_region_and_creds() -> None:
    storage_options = {
        "client_kwargs": {
            "endpoint_url": "http://example.com",
            "region_name": "us-west-2",
            "aws_access_key_id": "key",
        }
    }
    result = _apply_pandas_storage_options(
        storage_options, "http://server", AutoEndpointMode.FORCE
    )
    assert result is not None
    client_kwargs = result["client_kwargs"]
    assert client_kwargs["region_name"] == "us-west-2"
    assert client_kwargs["aws_access_key_id"] == "key"


def test_polars_storage_options_has_endpoint_detects_keys() -> None:
    assert _polars_storage_options_has_endpoint({"endpoint_url": "http://example.com"})
    assert _polars_storage_options_has_endpoint({"AWS_ENDPOINT_URL": "http://x"})
    assert not _polars_storage_options_has_endpoint({"endpoint_url": None})
    assert _polars_storage_options_has_endpoint(
        {"endpoint_url": None, "aws_endpoint_url": "http://example.com"}
    )


def test_polars_fsspec_has_endpoint_detects_keys() -> None:
    assert _polars_fsspec_has_endpoint({"endpoint_url": "http://example.com"})
    assert _polars_fsspec_has_endpoint(
        {"client_kwargs": {"endpoint_url": "http://example.com"}}
    )
    assert _polars_fsspec_has_endpoint({"client_kwargs": "bad"})
    assert not _polars_fsspec_has_endpoint({"anon": False})


def test_apply_polars_storage_options_respects_if_missing() -> None:
    storage_options = {"endpoint_url": "http://example.com"}
    result = _apply_polars_storage_options(
        storage_options, "http://server", AutoEndpointMode.IF_MISSING
    )
    assert result is storage_options


def test_apply_polars_storage_options_injects_endpoint() -> None:
    result = _apply_polars_storage_options(
        None, "http://server", AutoEndpointMode.FORCE
    )
    assert result is not None
    assert result["endpoint_url"] == "http://server"
    assert result["allow_http"] == "true"
    assert result["aws_region"] == "us-east-1"


def test_apply_polars_storage_options_noop_when_disabled() -> None:
    storage_options = {"endpoint_url": "http://example.com"}
    result = _apply_polars_storage_options(
        storage_options, "http://server", AutoEndpointMode.DISABLED
    )
    assert result is storage_options


def test_apply_polars_storage_options_injects_when_no_endpoint() -> None:
    storage_options: dict[str, object] = {"aws_region": "us-west-2"}
    result = _apply_polars_storage_options(
        storage_options, "http://server", AutoEndpointMode.IF_MISSING
    )
    assert result is not None
    assert result["endpoint_url"] == "http://server"


def test_apply_polars_fsspec_storage_options_injects_endpoint() -> None:
    result = _apply_polars_fsspec_storage_options(
        None, "http://server", AutoEndpointMode.FORCE
    )
    assert result is not None
    assert result["endpoint_url"] == "http://server"
    assert result["use_ssl"] is False
    assert result["config_kwargs"] == {"s3": {"addressing_style": "path"}}


def test_apply_polars_fsspec_storage_options_respects_if_missing() -> None:
    storage_options = {"client_kwargs": {"endpoint_url": "http://example.com"}}
    result = _apply_polars_fsspec_storage_options(
        storage_options, "http://server", AutoEndpointMode.IF_MISSING
    )
    assert result is storage_options


def test_apply_polars_fsspec_storage_options_respects_disabled() -> None:
    storage_options = {"endpoint_url": "http://example.com"}
    result = _apply_polars_fsspec_storage_options(
        storage_options, "http://server", AutoEndpointMode.DISABLED
    )
    assert result is storage_options


def test_apply_polars_fsspec_storage_options_sets_region_when_missing() -> None:
    storage_options: dict[str, object] = {"client_kwargs": {}}
    result = _apply_polars_fsspec_storage_options(
        storage_options, "http://server", AutoEndpointMode.IF_MISSING
    )
    assert result is not None
    assert result["endpoint_url"] == "http://server"
    assert result["client_kwargs"]["region_name"] == "us-east-1"


def test_apply_polars_fsspec_storage_options_preserves_bad_client_kwargs() -> None:
    storage_options: dict[str, object] = {"client_kwargs": "bad"}
    result = _apply_polars_fsspec_storage_options(
        storage_options, "http://server", AutoEndpointMode.FORCE
    )
    assert result is not None
    assert result["endpoint_url"] == "http://server"
    assert result["client_kwargs"] == "bad"


def test_wrap_polars_write_ndjson_noop_for_non_s3() -> None:
    called: dict[str, object] = {}

    def _original(self: object, file: str | None = None) -> str:
        called["file"] = file
        return "ok"

    wrapped = _wrap_polars_write_ndjson(
        _original, lambda: ("http://server", AutoEndpointMode.FORCE)
    )
    result = wrapped(object(), file="local/file")
    assert result == "ok"
    assert called["file"] == "local/file"


def test_wrap_polars_write_ndjson_respects_disabled_mode(mocker: MockerFixture) -> None:
    called: dict[str, object] = {}
    obj = mocker.Mock()
    obj.lazy = mocker.Mock()

    def _original(self: object, file: str | None = None) -> str:
        called["file"] = file
        return "ok"

    wrapped = _wrap_polars_write_ndjson(
        _original, lambda: ("http://server", AutoEndpointMode.DISABLED)
    )
    result = wrapped(obj, "s3://bucket/key")
    assert result == "ok"
    assert called["file"] == "s3://bucket/key"
    obj.lazy.assert_not_called()


def test_wrap_polars_write_ndjson_noop_when_self_missing() -> None:
    called: dict[str, object] = {}

    def _original(self: object, file: str | None = None) -> str:
        called["file"] = file
        return "ok"

    wrapped = _wrap_polars_write_ndjson(
        _original, lambda: ("http://server", AutoEndpointMode.FORCE)
    )
    result = wrapped(None, "s3://bucket/key")
    assert result == "ok"
    assert called["file"] == "s3://bucket/key"


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


def test_patch_s3fs_if_missing_respects_user_kwargs(
    monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture
) -> None:
    class _S3FileSystem:  # noqa: B903
        def __init__(
            self,
            *,
            anon: bool | None = None,
            endpoint_url: str | None = None,
            client_kwargs: dict[str, object] | None = None,
            config_kwargs: dict[str, object] | None = None,
            use_ssl: bool | None = None,
        ) -> None:
            self.anon = anon
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
    patcher._mode = AutoEndpointMode.IF_MISSING
    patcher._patch_s3fs()
    fs = s3fs_core.S3FileSystem(anon=True)
    assert fs.endpoint_url is None
    assert fs.client_kwargs is None
    patcher._restore_s3fs()


def test_patch_pandas_skips_when_missing(mocker: MockerFixture) -> None:
    patcher = ServerModePatcher()
    mocker.patch(
        "aiomoto.patches.server_mode.importlib.util.find_spec", return_value=None
    )
    patcher._patch_pandas()
    assert patcher._original_pandas_get_filepath is None


def test_patch_polars_skips_when_missing(mocker: MockerFixture) -> None:
    patcher = ServerModePatcher()
    mocker.patch(
        "aiomoto.patches.server_mode.importlib.util.find_spec", return_value=None
    )
    patcher._patch_polars()
    assert patcher._original_polars_functions is None


def test_polars_modules_skip_when_classes_missing(
    monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture
) -> None:
    polars_module = ModuleType("polars")
    for name, value in {"DataFrame": None, "LazyFrame": object()}.items():
        setattr(polars_module, name, value)
    monkeypatch.setitem(sys.modules, "polars", polars_module)
    mocker.patch(
        "aiomoto.patches.server_mode.importlib.util.find_spec", return_value=object()
    )
    assert _polars_modules() is None


def test_pandas_modules_skip_on_free_threaded(mocker: MockerFixture) -> None:
    find_spec = mocker.patch("aiomoto.patches.server_mode.importlib.util.find_spec")
    mocker.patch("aiomoto.patches.server_mode.sysconfig.get_config_var", return_value=1)
    assert _pandas_modules() is None
    find_spec.assert_not_called()


def test_pandas_modules_skip_when_fsspec_missing(mocker: MockerFixture) -> None:
    mocker.patch(
        "aiomoto.patches.server_mode.importlib.util.find_spec",
        side_effect=[object(), None],
    )
    assert _pandas_modules() is None


def test_pandas_modules_skip_when_s3fs_missing(mocker: MockerFixture) -> None:
    mocker.patch(
        "aiomoto.patches.server_mode.importlib.util.find_spec",
        side_effect=[object(), object(), None],
    )
    assert _pandas_modules() is None


def test_require_server_settings_raises() -> None:
    with pytest.raises(RuntimeError, match="auto-endpoint not configured"):
        _require_server_settings(None, None)


def test_patch_pandas_injects_storage_options(
    monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture
) -> None:
    _skip_if_free_threaded()
    pandas_module = ModuleType("pandas")
    pandas_io = ModuleType("pandas.io")
    pandas_common = ModuleType("pandas.io.common")
    pandas_parquet = ModuleType("pandas.io.parquet")

    def _get_filepath_or_buffer(
        filepath_or_buffer: object,
        encoding: str = "utf-8",
        compression: object | None = None,
        mode: str = "r",
        storage_options: dict[str, object] | None = None,
    ) -> dict[str, object] | None:
        return storage_options

    def _get_path_or_handle(
        path_or_handle: object,
        fs: object | None,
        mode: str,
        storage_options: dict[str, object] | None = None,
    ) -> dict[str, object] | None:
        return storage_options

    filepath_name = "_get_filepath_or_buffer"
    path_name = "_get_path_or_handle"
    setattr(pandas_common, filepath_name, _get_filepath_or_buffer)
    setattr(pandas_parquet, path_name, _get_path_or_handle)
    monkeypatch.setitem(sys.modules, "pandas", pandas_module)
    monkeypatch.setitem(sys.modules, "pandas.io", pandas_io)
    monkeypatch.setitem(sys.modules, "pandas.io.common", pandas_common)
    monkeypatch.setitem(sys.modules, "pandas.io.parquet", pandas_parquet)
    mocker.patch(
        "aiomoto.patches.server_mode.importlib.util.find_spec", return_value=object()
    )

    patcher = ServerModePatcher()
    patcher._endpoint = "http://localhost:5000"
    patcher._mode = AutoEndpointMode.FORCE
    patcher._patch_pandas()

    get_filepath = getattr(pandas_common, filepath_name)
    get_path = getattr(pandas_parquet, path_name)
    options = get_filepath("s3://bucket/key")
    assert options is not None
    assert options["endpoint_url"] == "http://localhost:5000"

    fs_options = {"client_kwargs": {"endpoint_url": "http://example.com"}}
    untouched = get_path("s3://bucket/key", object(), "rb", fs_options)
    assert untouched is fs_options

    patcher._restore_pandas()


def test_patch_polars_injects_storage_options(
    monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture
) -> None:
    polars_module = ModuleType("polars")

    def _read_parquet(
        *, source: object, storage_options: dict[str, object] | None = None
    ) -> dict[str, object] | None:
        return storage_options

    class _LazyFrame:
        def __init__(self) -> None:
            self.storage_options: dict[str, object] | None = None

        def sink_ndjson(
            self,
            path: str,
            *,
            storage_options: dict[str, object] | None = None,
            **_kwargs: object,
        ) -> None:
            self.storage_options = storage_options

    class _DataFrame:
        def __init__(self) -> None:
            self._lazy = _LazyFrame()

        def lazy(self) -> _LazyFrame:
            return self._lazy

        def write_parquet(
            self, file: str, *, storage_options: dict[str, object] | None = None
        ) -> dict[str, object] | None:
            return storage_options

        def write_ndjson(self, file: str | None = None) -> None:
            return None

    df_local = _DataFrame()
    assert df_local.write_ndjson() is None

    for name, value in {
        "read_parquet": _read_parquet,
        "DataFrame": _DataFrame,
        "LazyFrame": _LazyFrame,
    }.items():
        setattr(polars_module, name, value)
    monkeypatch.setitem(sys.modules, "polars", polars_module)
    mocker.patch(
        "aiomoto.patches.server_mode.importlib.util.find_spec", return_value=object()
    )

    patcher = ServerModePatcher()
    patcher._endpoint = "http://localhost:5000"
    patcher._mode = AutoEndpointMode.FORCE
    patcher._patch_polars()

    options = polars_module.read_parquet(source="s3://bucket/key")
    assert options is not None
    assert options["endpoint_url"] == "http://localhost:5000"
    local_options = polars_module.read_parquet(source="local/file")
    assert local_options is None

    df = polars_module.DataFrame()
    write_opts = df.write_parquet("s3://bucket/key")
    assert write_opts is not None
    assert write_opts["endpoint_url"] == "http://localhost:5000"

    df.write_ndjson("s3://bucket/key")
    storage_options = df.lazy().storage_options
    assert storage_options is not None
    assert storage_options["endpoint_url"] == "http://localhost:5000"

    patcher._restore_polars()


def test_patch_polars_noop_when_already_patched() -> None:
    patcher = ServerModePatcher()
    patcher._original_polars_functions = {}
    patcher._patch_polars()
    assert patcher._original_polars_functions == {}


def test_restore_polars_noop_when_missing() -> None:
    patcher = ServerModePatcher()
    patcher._restore_polars()


def test_restore_polars_restores_methods(monkeypatch: pytest.MonkeyPatch) -> None:
    polars_module = ModuleType("polars")

    class _DataFrame:
        def write_parquet(self) -> None:
            return None

    class _LazyFrame:
        def sink_parquet(self) -> None:
            return None

    df_local = _DataFrame()
    assert df_local.write_parquet() is None
    lazy_local = _LazyFrame()
    assert lazy_local.sink_parquet() is None

    for name, value in {"DataFrame": _DataFrame, "LazyFrame": _LazyFrame}.items():
        setattr(polars_module, name, value)
    monkeypatch.setitem(sys.modules, "polars", polars_module)

    patcher = ServerModePatcher()

    def _original_read() -> None:
        return None

    def _original_df(*_args: object, **_kwargs: object) -> None:
        return None

    def _original_lazy(*_args: object, **_kwargs: object) -> None:
        return None

    assert _original_read() is None
    assert _original_df() is None
    assert _original_lazy() is None

    patcher._original_polars_functions = {"read_parquet": _original_read}
    patcher._original_polars_df_methods = {"write_parquet": _original_df}
    patcher._original_polars_lazy_methods = {"sink_parquet": _original_lazy}
    patcher._restore_polars()
    assert polars_module.DataFrame.write_parquet is _original_df
    assert polars_module.LazyFrame.sink_parquet is _original_lazy


def test_restore_polars_skips_missing_methods(monkeypatch: pytest.MonkeyPatch) -> None:
    polars_module = ModuleType("polars")
    for name, value in {"DataFrame": object(), "LazyFrame": object()}.items():
        setattr(polars_module, name, value)
    monkeypatch.setitem(sys.modules, "polars", polars_module)

    patcher = ServerModePatcher()

    def _original_read() -> None:
        return None

    assert _original_read() is None

    patcher._original_polars_functions = {"read_parquet": _original_read}
    patcher._original_polars_df_methods = None
    patcher._original_polars_lazy_methods = None
    patcher._restore_polars()


def test_patch_pandas_noop_when_already_patched() -> None:
    patcher = ServerModePatcher()

    def _noop(*args: object, **kwargs: object) -> None:
        return None

    patcher._original_pandas_get_filepath = _noop
    patcher._patch_pandas()
    assert _noop() is None


def test_skip_if_free_threaded_skips(mocker: MockerFixture) -> None:
    mocker.patch("sysconfig.get_config_var", return_value=1)
    with pytest.raises(pytest.skip.Exception):
        _skip_if_free_threaded()


def test_restore_pandas_noop_when_missing() -> None:
    patcher = ServerModePatcher()
    patcher._restore_pandas()


def test_wrap_pandas_get_filepath_injects_storage_options() -> None:
    def _original(
        filepath_or_buffer: object,
        *args: object,
        storage_options: dict[str, object] | None = None,
        **kwargs: object,
    ) -> dict[str, object] | None:
        return storage_options

    def _get_settings() -> tuple[str, AutoEndpointMode]:
        return ("http://server", AutoEndpointMode.FORCE)

    wrapper = _wrap_pandas_get_filepath(_original, _get_settings)
    result = wrapper("s3://bucket/key")
    assert result is not None
    assert result["endpoint_url"] == "http://server"


def test_wrap_pandas_get_filepath_noop_for_non_s3() -> None:
    def _original(
        filepath_or_buffer: object,
        *args: object,
        storage_options: dict[str, object] | None = None,
        **kwargs: object,
    ) -> dict[str, object] | None:
        return storage_options

    def _get_settings() -> tuple[str, AutoEndpointMode]:
        return ("http://server", AutoEndpointMode.FORCE)

    wrapper = _wrap_pandas_get_filepath(_original, _get_settings)
    assert wrapper("file:///local/data.csv") is None


def test_wrap_pandas_get_path_injects_storage_options() -> None:
    def _original(
        path_or_handle: object,
        fs: object | None,
        mode: str,
        *args: object,
        storage_options: dict[str, object] | None = None,
        **kwargs: object,
    ) -> dict[str, object] | None:
        return storage_options

    def _get_settings() -> tuple[str, AutoEndpointMode]:
        return ("http://server", AutoEndpointMode.FORCE)

    wrapper = _wrap_pandas_get_path(_original, _get_settings)
    result = wrapper("s3://bucket/key", None, "rb")
    assert result is not None
    assert result["endpoint_url"] == "http://server"


def test_wrap_pandas_get_path_noop_for_non_s3() -> None:
    def _original(
        path_or_handle: object,
        fs: object | None,
        mode: str,
        *args: object,
        storage_options: dict[str, object] | None = None,
        **kwargs: object,
    ) -> dict[str, object] | None:
        return storage_options

    def _get_settings() -> tuple[str, AutoEndpointMode]:
        return ("http://server", AutoEndpointMode.FORCE)

    wrapper = _wrap_pandas_get_path(_original, _get_settings)
    options: dict[str, object] = {"client_kwargs": {"endpoint_url": "http://keep"}}
    assert wrapper("data.csv", None, "rb", storage_options=options) is options
