from __future__ import annotations

import asyncio

from moto import settings
import pytest

from aiomoto import mock_aws, mock_aws_decorator
from aiomoto.context import mock_aws as ctx_mock_aws
from aiomoto.exceptions import ProxyModeError, ServerModeRequiredError


def test_mock_aws_as_context_allows_config_kwargs() -> None:
    with mock_aws(config={"lambda": {"use_docker": False}}):
        # If no exception is raised, config flowed through to Moto.
        assert True


def test_mock_aws_as_decorator_allows_config_kwargs() -> None:
    calls = []

    @mock_aws(config={"lambda": {"use_docker": False}})
    def decorated() -> None:
        calls.append("run")

    decorated()
    assert calls == ["run"]


def test_mock_aws_decorator_factory_accepts_config() -> None:
    deco = mock_aws_decorator(config={"lambda": {"use_docker": False}})

    @deco
    def decorated() -> None:
        return None

    decorated()  # Should not raise


@pytest.mark.asyncio
async def test_mock_aws_async_decorator() -> None:
    calls: list[str] = []

    @mock_aws(config={"lambda": {"use_docker": False}})
    async def decorated() -> None:
        calls.append("run")
        await asyncio.sleep(0)

    await decorated()
    assert calls == ["run"]


def test_mock_aws_direct_import_sync_wrapper() -> None:
    called: list[str] = []

    @ctx_mock_aws(config={"lambda": {"use_docker": False}})
    def fn() -> None:
        called.append("x")

    fn()
    assert called == ["x"]


def test_mock_aws_decorator_no_args_sync() -> None:
    called: list[str] = []

    @mock_aws
    def fn() -> None:
        called.append("run")

    fn()
    assert called == ["run"]


@pytest.mark.asyncio
async def test_mock_aws_decorator_no_args_async() -> None:
    called: list[str] = []

    @mock_aws
    async def fn() -> None:
        called.append("run")
        await asyncio.sleep(0)

    await fn()
    assert called == ["run"]


def test_mock_aws_rejects_server_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "TEST_SERVER_MODE", True)
    with pytest.raises(ServerModeRequiredError, match="server_mode must be enabled"):
        mock_aws()


def test_mock_aws_rejects_proxy_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "is_test_proxy_mode", lambda: True)
    with pytest.raises(ProxyModeError, match="does not support Moto proxy mode"):
        mock_aws()
