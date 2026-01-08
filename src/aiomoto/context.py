"""Unified sync/async context manager that applies all aiomoto patches.

`mock_aws` mirrors moto's flexible surface:
1) Sync or async context manager: `with mock_aws(...):` / `async with mock_aws(...):`.
2) Decorator without args: `@mock_aws`.
3) Decorator with config/flags:
   `@mock_aws(config={...}, reset=False, remove_data=False)`.

The overloads + ParamSpec/TypeVar plumbing keep typing correct for both sync and async
callables while sharing one implementation.
"""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from contextlib import AbstractAsyncContextManager, AbstractContextManager, suppress
from functools import wraps
import importlib.util
import inspect
import json
import os
from pathlib import Path
import threading
import time
from typing import Any, no_type_check, overload, ParamSpec, TypeVar
from urllib import error, parse, request
import uuid

from moto import settings
from moto.core.decorator import mock_aws as moto_mock_aws
from moto.core.models import MockAWS
from platformdirs import user_cache_dir

from aiomoto.exceptions import (
    AutoEndpointError,
    InProcessModeError,
    ModeConflictError,
    ProxyModeError,
    ServerModeConfigurationError,
    ServerModeDependencyError,
    ServerModeEndpointError,
    ServerModeHealthcheckError,
    ServerModePortError,
    ServerModeRequiredError,
)
from aiomoto.patches.core import CorePatcher
from aiomoto.patches.server_mode import AutoEndpointMode, ServerModePatcher


P = ParamSpec("P")
R = TypeVar("R")
RA = TypeVar("RA")

_ENV_KEYS = (
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_SESSION_TOKEN",
    "AWS_DEFAULT_REGION",
    "AWS_REGION",
)
_SERVER_REGISTRY_ENV = "AIOMOTO_SERVER_REGISTRY_DIR"
_SERVER_PORT_ENV = "AIOMOTO_SERVER_PORT"
_SERVER_ENV_KEYS = (*_ENV_KEYS, _SERVER_REGISTRY_ENV, _SERVER_PORT_ENV)
_SERVER_REGISTRY_TTL_SECONDS = 24 * 60 * 60

_DEFAULT_ENV = {
    "AWS_ACCESS_KEY_ID": "test",
    "AWS_SECRET_ACCESS_KEY": "test",
    "AWS_SESSION_TOKEN": "test",
    "AWS_DEFAULT_REGION": "us-east-1",
    "AWS_REGION": "us-east-1",
}


def _snapshot_env(keys: tuple[str, ...] = _ENV_KEYS) -> dict[str, str | None]:
    return {key: os.environ.get(key) for key in keys}


def _apply_env_defaults() -> None:
    for key, value in _DEFAULT_ENV.items():
        if os.environ.get(key) is None:
            os.environ[key] = value


def _restore_env(snapshot: dict[str, str | None]) -> None:
    for key, value in snapshot.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


def _healthcheck(endpoint: str) -> None:
    parsed = parse.urlparse(endpoint)
    if parsed.scheme not in {"http", "https"}:
        raise ServerModeEndpointError(
            f"aiomoto server-mode healthcheck requires http(s) endpoint: {endpoint}"
        )
    health_url = f"{endpoint}/moto-api"
    try:
        with request.urlopen(health_url, timeout=2) as response:  # noqa: S310
            if response.status != 200:
                raise ServerModeHealthcheckError(
                    f"aiomoto server-mode healthcheck failed: {health_url}"
                )
    except (error.URLError, OSError) as exc:  # pragma: no cover - exercised via tests
        raise ServerModeHealthcheckError(
            f"aiomoto server-mode healthcheck failed: {health_url}"
        ) from exc


def _ensure_server_dependencies() -> None:
    if (
        importlib.util.find_spec("flask") is None
        or importlib.util.find_spec("flask_cors") is None
    ):
        raise ServerModeDependencyError(
            "aiomoto server_mode requires moto[server] dependencies (flask, "
            "flask-cors)."
        )


class _InProcessState:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._count = 0

    def active(self) -> bool:
        with self._lock:
            return self._count > 0

    def enter(self) -> None:
        with self._lock:
            if _SERVER_STATE.active():
                raise ModeConflictError(
                    "aiomoto server_mode cannot be combined with in-process mode."
                )
            self._count += 1

    def exit(self) -> None:
        with self._lock:
            if self._count > 0:
                self._count -= 1


class _ServerModeState:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._count = 0
        self._server: Any | None = None
        self._endpoint: str | None = None
        self._host: str | None = None
        self._port: int | None = None
        self._registry_path: str | None = None
        self._owns_server = False
        self._env_snapshot: dict[str, str | None] | None = None

    def active(self) -> bool:
        with self._lock:
            return self._count > 0

    def start(self, server_port: int | None) -> tuple[str, int, str, str | None]:
        with self._lock:
            if _INPROCESS_STATE.active():
                raise ModeConflictError(
                    "aiomoto server_mode cannot be combined with in-process mode."
                )
            if self._count == 0:
                self._start_server(server_port)
            elif server_port is not None and server_port != self._port:
                raise ServerModePortError(
                    "aiomoto server_mode server_port changed while active."
                )
            self._count += 1
            if self._host is None or self._port is None or self._endpoint is None:
                raise ServerModeEndpointError(
                    "aiomoto server-mode failed to capture endpoint."
                )
            registry_path = self._registry_path if server_port is None else None
            return self._host, self._port, self._endpoint, registry_path

    def stop(self) -> None:
        with self._lock:
            if self._count == 0:
                return
            self._count -= 1
            if self._count > 0:
                return
            if self._server is not None and self._owns_server:
                self._server.stop()
            self._server = None
            self._host = None
            self._port = None
            self._endpoint = None
            if self._owns_server:
                self._remove_registry_file()
            self._registry_path = None
            self._owns_server = False
            self._restore_env_snapshot()

    def _start_server(self, server_port: int | None) -> None:
        self._env_snapshot = _snapshot_env(_SERVER_ENV_KEYS)
        server: Any | None = None
        registry_path: str | None = None
        owns_server = False
        try:
            _apply_env_defaults()
            if server_port is None:
                _ensure_server_dependencies()
                server, host, port, endpoint = self._create_server()
                registry_path = self._write_registry_file(host, port, endpoint)
                registry_dir = str(Path(registry_path).parent)
                os.environ[_SERVER_REGISTRY_ENV] = registry_dir
                os.environ[_SERVER_PORT_ENV] = str(port)
                owns_server = True
            else:
                if server_port <= 0 or server_port > 65535:
                    raise ServerModePortError(
                        "aiomoto server_mode server_port must be in 1..65535."
                    )
                host = "127.0.0.1"
                port = server_port
                endpoint = f"http://{host}:{port}"
                _healthcheck(endpoint)
        except Exception:
            if server is not None:
                with suppress(Exception):
                    server.stop()
            self._restore_env_snapshot()
            raise
        self._server = server
        self._host = host
        self._port = port
        self._endpoint = endpoint
        self._registry_path = registry_path
        self._owns_server = owns_server

    def _create_server(self) -> tuple[Any, str, int, str]:
        from moto.moto_server.threaded_moto_server import ThreadedMotoServer

        server = ThreadedMotoServer(ip_address="127.0.0.1", port=0, verbose=False)
        success = False
        try:
            server.start()
            host, port = server.get_host_and_port()
            endpoint = f"http://{host}:{port}"
            _healthcheck(endpoint)
            success = True
        finally:
            if not success:
                with suppress(Exception):
                    server.stop()
        return server, host, port, endpoint

    def _registry_dir(self) -> Path:
        return Path(user_cache_dir("aiomoto"))

    def _cleanup_stale_registry(self) -> None:
        registry_dir = self._registry_dir()
        if not registry_dir.exists():
            return
        cutoff = time.time() - _SERVER_REGISTRY_TTL_SECONDS
        for path in registry_dir.glob("aiomoto-server-*.json"):
            with suppress(OSError):
                if path.stat().st_mtime < cutoff:
                    path.unlink(missing_ok=True)

    def _write_registry_file(self, host: str, port: int, endpoint: str) -> str:
        registry_dir = self._registry_dir()
        registry_dir.mkdir(parents=True, exist_ok=True)
        self._cleanup_stale_registry()
        token = uuid.uuid4().hex
        path = registry_dir / f"aiomoto-server-{token}.json"
        payload = {"endpoint": endpoint, "host": host, "port": port, "pid": os.getpid()}
        path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
        return str(path)

    def _remove_registry_file(self) -> None:
        if self._registry_path is None:
            return
        with suppress(OSError):
            Path(self._registry_path).unlink(missing_ok=True)

    def _restore_env_snapshot(self) -> None:
        if self._env_snapshot is not None:
            _restore_env(self._env_snapshot)
            self._env_snapshot = None


_INPROCESS_STATE = _InProcessState()
_SERVER_STATE = _ServerModeState()
_SERVER_PATCHER = ServerModePatcher()


def _normalize_auto_endpoint(
    auto_endpoint: AutoEndpointMode | None, server_mode: bool
) -> AutoEndpointMode:
    if auto_endpoint is None:
        mode = AutoEndpointMode.FORCE if server_mode else AutoEndpointMode.DISABLED
    else:
        mode = auto_endpoint
    if not server_mode and mode is not AutoEndpointMode.DISABLED:
        raise AutoEndpointError("aiomoto auto_endpoint requires server_mode=True.")
    return mode


class _MotoAsyncContext(AbstractAsyncContextManager, AbstractContextManager):
    """Moto context usable from both sync and async code."""

    def __init__(
        self,
        reset: bool = True,
        remove_data: bool = True,
        *,
        config: Any | None = None,
        server_mode: bool = False,
        server_port: int | None = None,
        auto_endpoint: AutoEndpointMode | None = None,
    ) -> None:
        if settings.is_test_proxy_mode():
            raise ProxyModeError("aiomoto does not support Moto proxy mode.")
        if settings.TEST_SERVER_MODE and not server_mode:
            raise ServerModeRequiredError(
                "aiomoto server_mode must be enabled when Moto server mode is active."
            )
        if server_mode and config is not None:
            raise ServerModeConfigurationError(
                "aiomoto server_mode does not accept config overrides."
            )
        if server_port is not None and not server_mode:
            raise ServerModeConfigurationError(
                "aiomoto server_port requires server_mode=True."
            )
        self._reset = reset
        self._remove_data = remove_data
        self._server_mode = server_mode
        self._server_port_override = server_port
        self._auto_endpoint = _normalize_auto_endpoint(auto_endpoint, server_mode)
        self._server_host: str | None = None
        self._server_port: int | None = None
        self._server_endpoint: str | None = None
        self._server_registry_path: str | None = None
        self._moto_context: MockAWS | None = None
        self._core: CorePatcher | None = None
        if self._server_mode:
            self._moto_context = None
            self._core = None
        else:
            moto_kwargs: dict[str, Any] = {}
            if config is not None:
                moto_kwargs["config"] = config
            self._moto_context = moto_mock_aws(**moto_kwargs)
            self._core = CorePatcher()
        self._depth = 0

    @property
    def _started(self) -> bool:
        """Backwards-compat alias for previous boolean flag."""

        return self._depth > 0

    @property
    def server_endpoint(self) -> str | None:
        return self._server_endpoint

    @property
    def server_host(self) -> str | None:
        return self._server_host

    @property
    def server_port(self) -> int | None:
        return self._server_port

    @property
    def server_registry_path(self) -> str | None:
        return self._server_registry_path

    def start(self, reset: bool | None = None) -> None:
        if self._server_mode:
            self._start_server_mode()
            return

        self._start_in_process(reset)

    def _start_server_mode(self) -> None:
        if self._depth == 0:
            host, port, endpoint, registry_path = _SERVER_STATE.start(
                self._server_port_override
            )
            started = False
            try:
                self._server_host = host
                self._server_port = port
                self._server_endpoint = endpoint
                self._server_registry_path = registry_path
                if self._auto_endpoint is not AutoEndpointMode.DISABLED:
                    _SERVER_PATCHER.start(endpoint, self._auto_endpoint)
                started = True
            finally:
                if not started:
                    _SERVER_STATE.stop()
                    self._server_host = None
                    self._server_port = None
                    self._server_endpoint = None
                    self._server_registry_path = None
        self._depth += 1

    def _start_in_process(self, reset: bool | None) -> None:
        starting_new = self._depth == 0
        if starting_new:
            _INPROCESS_STATE.enter()
            if self._core is None or not isinstance(self._moto_context, MockAWS):
                _INPROCESS_STATE.exit()
                raise InProcessModeError("aiomoto in-process mode not initialized.")
            try:
                self._core.start()
            except Exception:
                _INPROCESS_STATE.exit()
                raise
        try:
            if not isinstance(self._moto_context, MockAWS):
                raise InProcessModeError("aiomoto in-process mode not initialized.")
            self._moto_context.start(reset=reset if reset is not None else self._reset)
        except Exception as exc:
            if starting_new:
                if self._core is None:
                    raise InProcessModeError(
                        "aiomoto in-process mode not initialized."
                    ) from exc
                self._core.stop()
                _INPROCESS_STATE.exit()
            raise
        self._depth += 1

    def stop(self, remove_data: bool | None = None) -> None:
        if self._depth == 0:
            return
        if not self._server_mode:
            if not isinstance(self._moto_context, MockAWS):
                raise InProcessModeError("aiomoto in-process mode not initialized.")
            self._moto_context.stop(
                remove_data=remove_data
                if remove_data is not None
                else self._remove_data
            )
        self._depth -= 1
        if self._depth == 0:
            if self._server_mode:
                _SERVER_STATE.stop()
                if self._auto_endpoint is not AutoEndpointMode.DISABLED:
                    _SERVER_PATCHER.stop()
                self._server_host = None
                self._server_port = None
                self._server_endpoint = None
                self._server_registry_path = None
            else:
                if self._core is None:
                    raise InProcessModeError("aiomoto in-process mode not initialized.")
                self._core.stop()
                _INPROCESS_STATE.exit()

    # Sync context protocol ----------------------------------------------------
    def __enter__(self) -> _MotoAsyncContext:
        self.start()
        return self

    def __exit__(self, *args: Any) -> None:
        self.stop()

    # Async context protocol ---------------------------------------------------
    async def __aenter__(self) -> _MotoAsyncContext:
        self.start()
        return self

    async def __aexit__(self, *args: Any) -> None:
        self.stop()

    # Decorator protocol ------------------------------------------------------
    @overload
    def __call__(
        self, func: Callable[P, Coroutine[Any, Any, RA]]
    ) -> Callable[P, Coroutine[Any, Any, RA]]: ...

    @overload
    def __call__(self, func: Callable[P, R]) -> Callable[P, R]: ...

    @no_type_check
    def __call__(self, func: Callable[P, object]) -> Callable[P, object]:
        """Allow ``@mock_aws()`` on sync or async callables.

        The same context instance wraps each invocation, starting Moto before the
        function runs and stopping it afterwards. This keeps decorator semantics in
        line with the context manager without duplicating state handling.

        Returns:
            A callable that executes the wrapped function inside the mock context.
        """

        if inspect.iscoroutinefunction(func):
            async_func = func

            @wraps(func)
            async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> object:
                async with self:
                    return await async_func(*args, **kwargs)

            return async_wrapper

        sync_func = func

        @wraps(sync_func)
        def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> object:
            with self:
                return sync_func(*args, **kwargs)

        return sync_wrapper


@overload
def mock_aws_decorator(
    func: Callable[P, Coroutine[Any, Any, RA]], /
) -> Callable[P, Coroutine[Any, Any, RA]]: ...


@overload
def mock_aws_decorator(func: Callable[P, R], /) -> Callable[P, R]: ...


@overload
def mock_aws_decorator(
    func: None = ...,
    *,
    reset: bool = True,
    remove_data: bool = True,
    config: Any | None = None,
    server_mode: bool = False,
    server_port: int | None = None,
    auto_endpoint: AutoEndpointMode | None = None,
) -> _MotoAsyncContext: ...


def mock_aws_decorator(
    func: Callable[P, object] | None = None,
    *,
    reset: bool = True,
    remove_data: bool = True,
    config: Any | None = None,
    server_mode: bool = False,
    server_port: int | None = None,
    auto_endpoint: AutoEndpointMode | None = None,
) -> Any:
    """Decorator factory mirroring Moto's ``mock_aws`` wrapper.

    Parentheses are optional: ``@mock_aws_decorator`` uses defaults, while
    ``@mock_aws_decorator(config={...})`` lets callers preconfigure behaviour.

    Returns:
        Either a wrapped callable (when used as ``@mock_aws_decorator``) or a
        reusable context/decorator instance when invoked with keyword arguments.
    """

    context = _MotoAsyncContext(
        reset=reset,
        remove_data=remove_data,
        config=config,
        server_mode=server_mode,
        server_port=server_port,
        auto_endpoint=auto_endpoint,
    )

    if func is None:
        return context

    return context(func)


@overload
def mock_aws(
    func: Callable[P, Coroutine[Any, Any, RA]], /
) -> Callable[P, Coroutine[Any, Any, RA]]: ...


@overload
def mock_aws(func: Callable[P, R], /) -> Callable[P, R]: ...


@overload
def mock_aws(
    func: None = ...,
    *,
    reset: bool = True,
    remove_data: bool = True,
    config: Any | None = None,
    server_mode: bool = False,
    server_port: int | None = None,
    auto_endpoint: AutoEndpointMode | None = None,
) -> _MotoAsyncContext: ...


def mock_aws(
    func: Callable[P, object] | None = None,
    *,
    reset: bool = True,
    remove_data: bool = True,
    config: Any | None = None,
    server_mode: bool = False,
    server_port: int | None = None,
    auto_endpoint: AutoEndpointMode | None = None,
) -> Any:
    """Factory/decorator mirroring Moto's ``mock_aws`` (config supported).

    Returns:
        A decorated callable when used as a decorator, or a context manager when
        called with no function.
    """

    context = _MotoAsyncContext(
        reset=reset,
        remove_data=remove_data,
        config=config,
        server_mode=server_mode,
        server_port=server_port,
        auto_endpoint=auto_endpoint,
    )

    if func is None:
        return context

    if inspect.iscoroutinefunction(func):

        @wraps(func)
        async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> Any:
            async with context:
                return await func(*args, **kwargs)

        return async_wrapper

    @wraps(func)
    def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> Any:
        with context:
            return func(*args, **kwargs)

    return sync_wrapper
