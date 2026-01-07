from __future__ import annotations

from types import SimpleNamespace
from urllib import error

import pytest
from pytest_mock import MockerFixture

from aiomoto.context import (
    _ensure_server_dependencies,
    _healthcheck,
    _InProcessState,
    _MotoAsyncContext,
    _normalize_auto_endpoint,
    _ServerModeState,
)
from aiomoto.exceptions import (
    AutoEndpointError,
    InProcessModeError,
    ModeConflictError,
    ServerModeConfigurationError,
    ServerModeDependencyError,
    ServerModeEndpointError,
    ServerModeHealthcheckError,
    ServerModePortError,
)
from aiomoto.patches.server_mode import AutoEndpointMode


def _require_server_deps() -> None:
    pytest.importorskip("flask")
    pytest.importorskip("flask_cors")


def test_healthcheck_rejects_non_http_scheme() -> None:
    with pytest.raises(ServerModeEndpointError, match="http"):
        _healthcheck("ftp://example.com")


def test_healthcheck_rejects_non_200(mocker: MockerFixture) -> None:
    class _Response:
        status = 500

        def __enter__(self) -> _Response:
            return self

        def __exit__(
            self,
            exc_type: type[BaseException] | None,
            exc: BaseException | None,
            tb: object | None,
        ) -> None:
            return None

    mocker.patch("aiomoto.context.request.urlopen", return_value=_Response())
    with pytest.raises(ServerModeHealthcheckError, match="healthcheck failed"):
        _healthcheck("http://example.com")


def test_healthcheck_wraps_urlopen_errors(mocker: MockerFixture) -> None:
    mocker.patch("aiomoto.context.request.urlopen", side_effect=error.URLError("boom"))
    with pytest.raises(ServerModeHealthcheckError, match="healthcheck failed"):
        _healthcheck("http://example.com")


def test_ensure_server_dependencies_missing(mocker: MockerFixture) -> None:
    mocker.patch(
        "aiomoto.context.importlib.util.find_spec", side_effect=lambda name: None
    )
    with pytest.raises(ServerModeDependencyError, match="moto\\[server\\]"):
        _ensure_server_dependencies()


def test_inprocess_enter_rejects_server_mode(mocker: MockerFixture) -> None:
    mocker.patch("aiomoto.context._SERVER_STATE.active", return_value=True)
    state = _InProcessState()
    with pytest.raises(ModeConflictError, match="server_mode"):
        state.enter()


def test_inprocess_exit_noop_when_zero() -> None:
    state = _InProcessState()
    state.exit()
    assert state.active() is False


def test_server_state_start_rejects_inprocess(mocker: MockerFixture) -> None:
    mocker.patch("aiomoto.context._INPROCESS_STATE.active", return_value=True)
    state = _ServerModeState()
    with pytest.raises(ModeConflictError, match="server_mode"):
        state.start(server_port=None)


def test_server_state_start_requires_endpoint(mocker: MockerFixture) -> None:
    state = _ServerModeState()
    mocker.patch.object(state, "_start_server", return_value=None)
    with pytest.raises(ServerModeEndpointError, match="capture endpoint"):
        state.start(server_port=None)


def test_server_state_start_rejects_invalid_port() -> None:
    state = _ServerModeState()
    with pytest.raises(ServerModePortError, match=r"server_port must be in 1\.\.65535"):
        state.start(server_port=0)


def test_server_state_start_rejects_port_change() -> None:
    state = _ServerModeState()
    state._count = 1
    state._port = 1234
    with pytest.raises(ServerModePortError, match="server_port changed"):
        state.start(server_port=4321)


def test_server_state_stop_noop_when_zero() -> None:
    state = _ServerModeState()
    state.stop()


def test_server_state_stop_stops_server(mocker: MockerFixture) -> None:
    state = _ServerModeState()
    server = SimpleNamespace(stop=mocker.Mock())
    state._count = 1
    state._server = server
    state._owns_server = True
    state._env_snapshot = {}
    state.stop()
    server.stop.assert_called_once_with()


def test_server_state_stop_without_server() -> None:
    state = _ServerModeState()
    state._count = 1
    state._server = None
    state.stop()


def test_server_state_restore_env_snapshot_noop() -> None:
    state = _ServerModeState()
    state._restore_env_snapshot()


def test_server_state_start_attach_uses_healthcheck(mocker: MockerFixture) -> None:
    state = _ServerModeState()
    healthcheck = mocker.patch("aiomoto.context._healthcheck")
    host, port, endpoint, registry_path = state.start(server_port=1234)
    assert host == "127.0.0.1"
    assert port == 1234
    assert endpoint == "http://127.0.0.1:1234"
    assert registry_path is None
    healthcheck.assert_called_once_with(endpoint)
    state.stop()


def test_server_state_start_cleanup_on_registry_failure(mocker: MockerFixture) -> None:
    state = _ServerModeState()
    mocker.patch("aiomoto.context._ensure_server_dependencies")

    class _Server:
        def __init__(self) -> None:
            self.stop = mocker.Mock()

    server = _Server()

    def _create_server() -> tuple[object, str, int, str]:
        return server, "127.0.0.1", 4321, "http://127.0.0.1:4321"

    mocker.patch.object(state, "_create_server", side_effect=_create_server)
    mocker.patch.object(state, "_write_registry_file", side_effect=RuntimeError("boom"))

    with pytest.raises(RuntimeError, match="boom"):
        state.start(server_port=None)

    server.stop.assert_called_once_with()


def test_normalize_auto_endpoint_rejects_without_server_mode() -> None:
    with pytest.raises(AutoEndpointError, match="server_mode=True"):
        _normalize_auto_endpoint(AutoEndpointMode.FORCE, server_mode=False)


def test_context_rejects_config_in_server_mode() -> None:
    with pytest.raises(ServerModeConfigurationError, match="config overrides"):
        _MotoAsyncContext(server_mode=True, config={"s3": {}})


def test_context_rejects_server_port_without_server_mode() -> None:
    with pytest.raises(ServerModeConfigurationError, match="server_port requires"):
        _MotoAsyncContext(server_port=1234)


def test_context_server_properties_default_to_none() -> None:
    context = _MotoAsyncContext(server_mode=True)
    assert context.server_endpoint is None
    assert context.server_host is None
    assert context.server_port is None
    assert context.server_registry_path is None


def test_server_mode_disabled_skips_patcher(mocker: MockerFixture) -> None:
    mocker.patch(
        "aiomoto.context._SERVER_STATE.start",
        return_value=("127.0.0.1", 1234, "http://127.0.0.1:1234", None),
    )
    mocker.patch("aiomoto.context._SERVER_STATE.stop")
    mocker.patch("aiomoto.context._SERVER_PATCHER.start", side_effect=AssertionError)
    mocker.patch("aiomoto.context._SERVER_PATCHER.stop", side_effect=AssertionError)
    context = _MotoAsyncContext(
        server_mode=True, auto_endpoint=AutoEndpointMode.DISABLED
    )
    context.start()
    context.stop()


def test_start_in_process_rejects_uninitialized_core(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from aiomoto import context as context_module

    state = _InProcessState()
    monkeypatch.setattr(context_module, "_INPROCESS_STATE", state)
    context = _MotoAsyncContext()
    context._core = None
    context._moto_context = None
    with pytest.raises(InProcessModeError, match="in-process mode not initialized"):
        context._start_in_process(reset=None)
    state.exit()


def test_start_in_process_failure_cleans_up(
    monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture
) -> None:
    from aiomoto import context as context_module

    state = _InProcessState()
    monkeypatch.setattr(context_module, "_INPROCESS_STATE", state)
    context = _MotoAsyncContext()
    context._core = mocker.Mock()
    mocker.patch.object(context._core, "start")
    mocker.patch.object(context._core, "stop")
    mocker.patch.object(
        context._moto_context, "start", side_effect=RuntimeError("boom")
    )
    with pytest.raises(RuntimeError, match="boom"):
        context._start_in_process(reset=None)
    context._core.stop.assert_called_once_with()
    assert state.active() is False


def test_start_in_process_core_start_failure_cleans_up(
    monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture
) -> None:
    from aiomoto import context as context_module

    state = _InProcessState()
    monkeypatch.setattr(context_module, "_INPROCESS_STATE", state)
    context = _MotoAsyncContext()
    context._core = mocker.Mock()
    mocker.patch.object(context._core, "start", side_effect=RuntimeError("boom"))
    mocker.patch.object(context._core, "stop")
    with pytest.raises(RuntimeError, match="boom"):
        context._start_in_process(reset=None)
    context._core.stop.assert_not_called()
    assert state.active() is False


def test_start_in_process_rejects_invalid_context_when_reused() -> None:
    context = _MotoAsyncContext()
    context._depth = 1
    context._moto_context = None
    with pytest.raises(InProcessModeError, match="in-process mode not initialized"):
        context._start_in_process(reset=None)


def test_stop_in_process_rejects_invalid_context() -> None:
    context = _MotoAsyncContext()
    context._depth = 1
    context._moto_context = None
    with pytest.raises(InProcessModeError, match="in-process mode not initialized"):
        context.stop()


def test_stop_in_process_rejects_missing_core(mocker: MockerFixture) -> None:
    context = _MotoAsyncContext()
    mocker.patch.object(context._moto_context, "stop")
    context._core = None
    context._depth = 1
    with pytest.raises(InProcessModeError, match="in-process mode not initialized"):
        context.stop()


def test_start_server_mode_reentry_skips_server_start(mocker: MockerFixture) -> None:
    start = mocker.patch(
        "aiomoto.context._SERVER_STATE.start",
        return_value=("127.0.0.1", 1234, "http://127.0.0.1:1234", None),
    )
    mocker.patch("aiomoto.context._SERVER_STATE.stop")
    mocker.patch("aiomoto.context._SERVER_PATCHER.start")
    mocker.patch("aiomoto.context._SERVER_PATCHER.stop")
    context = _MotoAsyncContext(server_mode=True)
    context.start()
    context.start()
    context.stop()
    context.stop()
    assert start.call_count == 1


def test_start_in_process_core_none_after_start(
    monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture
) -> None:
    from aiomoto import context as context_module

    state = _InProcessState()
    monkeypatch.setattr(context_module, "_INPROCESS_STATE", state)
    context = _MotoAsyncContext()
    context._core = mocker.Mock()
    mocker.patch.object(context._core, "start")

    def _boom(*args: object, **kwargs: object) -> None:
        context._core = None
        raise RuntimeError("boom")

    mocker.patch.object(context._moto_context, "start", side_effect=_boom)
    with pytest.raises(InProcessModeError, match="in-process mode not initialized"):
        context._start_in_process(reset=None)
    state.exit()


def test_create_server_cleans_up_on_failure(mocker: MockerFixture) -> None:
    _require_server_deps()
    stop = mocker.Mock()

    class _FakeServer:
        def __init__(self, *args: object, **kwargs: object) -> None:
            return None

        def start(self) -> None:
            return None

        def get_host_and_port(self) -> tuple[str, int]:
            return ("127.0.0.1", 1234)

        def stop(self) -> None:
            stop()

    mocker.patch(
        "moto.moto_server.threaded_moto_server.ThreadedMotoServer", _FakeServer
    )
    mocker.patch("aiomoto.context._healthcheck", side_effect=RuntimeError("boom"))
    state = _ServerModeState()
    with pytest.raises(RuntimeError, match="boom"):
        state._create_server()
    stop.assert_called_once_with()
