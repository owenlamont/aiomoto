from __future__ import annotations

import os
import pathlib
import sys
import time
from urllib import error, parse, request

import orjson
import pytest
from pytest_mock import MockerFixture

from aiomoto import AutoEndpointMode, mock_aws
from aiomoto.exceptions import AutoEndpointError


pytest.importorskip("flask")
pytest.importorskip("flask_cors")


def _assert_server_up(endpoint: str) -> None:
    parsed = parse.urlparse(endpoint)
    if parsed.scheme not in {"http", "https"}:
        raise AssertionError(f"Unexpected moto server endpoint: {endpoint}")
    with request.urlopen(f"{endpoint}/moto-api", timeout=2) as response:  # noqa: S310
        assert response.status == 200


def _assert_server_down(endpoint: str) -> None:
    for _ in range(10):
        if not _server_responding(endpoint):
            return
        time.sleep(0.1)
    raise AssertionError("Moto server still responding after shutdown")


def _server_responding(endpoint: str) -> bool:
    try:
        with request.urlopen(f"{endpoint}/moto-api", timeout=0.5):  # noqa: S310
            return True
    except (error.URLError, OSError):
        return False


def test_server_mode_starts_server_and_healthchecks() -> None:
    with mock_aws(server_mode=True) as ctx:
        assert ctx.server_endpoint is not None
        endpoint = ctx.server_endpoint
        _assert_server_up(endpoint)
    _assert_server_down(endpoint)


def test_server_mode_nested_contexts_share_server() -> None:
    with mock_aws(server_mode=True) as outer:
        endpoint = outer.server_endpoint
        assert endpoint is not None
        with mock_aws(server_mode=True) as inner:
            assert inner.server_endpoint == endpoint
            _assert_server_up(endpoint)
        _assert_server_up(endpoint)
    _assert_server_down(endpoint)


def test_server_mode_nested_mismatch_rolls_back() -> None:
    with mock_aws(server_mode=True, auto_endpoint=AutoEndpointMode.FORCE) as outer:
        endpoint = outer.server_endpoint
        assert endpoint is not None
        with pytest.raises(AutoEndpointError):
            mock_aws(
                server_mode=True, auto_endpoint=AutoEndpointMode.IF_MISSING
            ).__enter__()
        _assert_server_up(endpoint)
    _assert_server_down(endpoint)


def test_server_mode_preserves_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "orig")
    monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)
    monkeypatch.delenv("AWS_DEFAULT_REGION", raising=False)
    with mock_aws(server_mode=True):
        assert os.environ["AWS_ACCESS_KEY_ID"] == "orig"
        assert os.environ["AWS_SECRET_ACCESS_KEY"] == "test"  # noqa: S105
        assert os.environ["AWS_DEFAULT_REGION"] == "us-east-1"
    assert os.environ["AWS_ACCESS_KEY_ID"] == "orig"
    assert "AWS_SECRET_ACCESS_KEY" not in os.environ
    assert "AWS_DEFAULT_REGION" not in os.environ


def test_server_mode_dependency_failure_restores_env(
    monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture
) -> None:
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "orig")
    monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)
    monkeypatch.delenv("AWS_DEFAULT_REGION", raising=False)

    def _raise_missing() -> None:
        raise RuntimeError("missing deps")

    mocker.patch(
        "aiomoto.context._ensure_server_dependencies", side_effect=_raise_missing
    )

    with pytest.raises(RuntimeError, match="missing deps"):
        mock_aws(server_mode=True).__enter__()

    assert os.environ["AWS_ACCESS_KEY_ID"] == "orig"
    assert "AWS_SECRET_ACCESS_KEY" not in os.environ
    assert "AWS_DEFAULT_REGION" not in os.environ


def test_server_mode_registry_written_and_cleaned(
    monkeypatch: pytest.MonkeyPatch, tmp_path_factory: pytest.TempPathFactory
) -> None:
    registry_dir = tmp_path_factory.mktemp("aiomoto")
    monkeypatch.setenv("AIOMOTO_SERVER_REGISTRY_DIR", "orig")
    monkeypatch.setenv("AIOMOTO_SERVER_PORT", "42")
    monkeypatch.setattr(
        "aiomoto.context.user_cache_dir", lambda name: str(registry_dir)
    )

    with mock_aws(server_mode=True) as ctx:
        assert os.environ["AIOMOTO_SERVER_REGISTRY_DIR"] == str(registry_dir)
        assert os.environ["AIOMOTO_SERVER_PORT"] == str(ctx.server_port)
        registry_path = ctx.server_registry_path
        assert registry_path is not None
        payload = orjson.loads(pathlib.Path(registry_path).read_bytes())
        assert payload["endpoint"] == ctx.server_endpoint
        assert payload["host"] == ctx.server_host
        assert payload["port"] == ctx.server_port
        assert payload["pid"] == os.getpid()

    assert os.environ["AIOMOTO_SERVER_REGISTRY_DIR"] == "orig"
    assert os.environ["AIOMOTO_SERVER_PORT"] == "42"
    assert not pathlib.Path(registry_path).exists()


def test_server_mode_attach_preserves_owner() -> None:
    with mock_aws(server_mode=True) as owner:
        port = owner.server_port
        assert port is not None
        endpoint = owner.server_endpoint
        assert endpoint is not None
        _assert_server_up(endpoint)
        with mock_aws(server_mode=True, server_port=port) as attached:
            assert attached.server_endpoint == endpoint
            assert attached.server_registry_path is None
        _assert_server_up(endpoint)
    _assert_server_down(endpoint)


def test_assert_server_up_rejects_invalid_scheme() -> None:
    with pytest.raises(AssertionError, match="Unexpected moto server endpoint"):
        _assert_server_up("ftp://example.com")


def test_assert_server_down_raises_when_server_stays_up(mocker: MockerFixture) -> None:
    mocker.patch.object(sys.modules[__name__], "_server_responding", return_value=True)
    mocker.patch.object(time, "sleep")
    with pytest.raises(AssertionError, match="still responding"):
        _assert_server_down("http://example.com")


def test_server_responding_returns_true(mocker: MockerFixture) -> None:
    class _Response:
        def __enter__(self) -> _Response:
            return self

        def __exit__(
            self,
            exc_type: type[BaseException] | None,
            exc: BaseException | None,
            tb: object | None,
        ) -> None:
            return None

    mocker.patch.object(request, "urlopen", return_value=_Response())
    assert _server_responding("http://example.com") is True
