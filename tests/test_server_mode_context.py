from __future__ import annotations

import os
import time
from urllib import error, parse, request

import pytest

from aiomoto import mock_aws


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
