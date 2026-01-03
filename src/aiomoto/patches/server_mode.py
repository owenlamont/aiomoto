"""Server-mode patching for auto-endpoint injection."""

from __future__ import annotations

from collections.abc import Callable
from enum import Enum
import importlib.util
import inspect
import os
import threading
from typing import Any

from botocore.config import Config
from botocore.session import Session as BotocoreSession


class AutoEndpointMode(str, Enum):
    FORCE = "force"
    IF_MISSING = "if_missing"
    DISABLED = "disabled"


def _default_region() -> str:
    return (
        os.environ.get("AWS_REGION")
        or os.environ.get("AWS_DEFAULT_REGION")
        or "us-east-1"
    )


def _default_creds() -> tuple[str, str, str | None]:
    access_key = os.environ.get("AWS_ACCESS_KEY_ID", "test")
    secret_key = os.environ.get("AWS_SECRET_ACCESS_KEY", "test")
    token = os.environ.get("AWS_SESSION_TOKEN")
    return access_key, secret_key, token


def _should_inject(mode: AutoEndpointMode, endpoint_url: str | None) -> bool:
    if mode is AutoEndpointMode.DISABLED:
        return False
    if mode is AutoEndpointMode.FORCE:
        return True
    return endpoint_url is None


def _merge_path_style(config: Any | None) -> Any:
    path_style = Config(s3={"addressing_style": "path"})
    if config is None:
        return path_style
    merge = getattr(config, "merge", None)
    if callable(merge):
        return merge(path_style)
    return config


def _apply_client_defaults(
    arguments: dict[str, Any], endpoint: str, mode: AutoEndpointMode
) -> None:
    endpoint_url = arguments.get("endpoint_url")
    if not _should_inject(mode, endpoint_url):
        return
    arguments["endpoint_url"] = endpoint
    arguments["use_ssl"] = False
    if arguments.get("region_name") is None:
        arguments["region_name"] = _default_region()
    if arguments.get("aws_access_key_id") is None:
        access_key, secret_key, token = _default_creds()
        arguments["aws_access_key_id"] = access_key
        arguments["aws_secret_access_key"] = secret_key
        if arguments.get("aws_session_token") is None and token is not None:
            arguments["aws_session_token"] = token
    arguments["config"] = _merge_path_style(arguments.get("config"))


class ServerModePatcher:
    """Patch client creation to auto-inject the moto server endpoint."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._count = 0
        self._endpoint: str | None = None
        self._mode: AutoEndpointMode | None = None
        self._original_botocore_create: Callable[..., Any] | None = None
        self._original_aio_create: Callable[..., Any] | None = None
        self._original_s3fs_init: Callable[..., Any] | None = None

    def start(self, endpoint: str, mode: AutoEndpointMode) -> None:
        """Apply auto-endpoint patches (refcounted).

        Raises:
            RuntimeError: If the active server-mode settings change mid-flight.
        """
        with self._lock:
            if self._count == 0:
                self._endpoint = endpoint
                self._mode = mode
                self._patch_botocore()
                self._patch_aiobotocore()
                self._patch_s3fs()
            else:
                if endpoint != self._endpoint or mode != self._mode:
                    raise RuntimeError(
                        "aiomoto server_mode auto-endpoint settings changed while "
                        "active."
                    )
            self._count += 1

    def stop(self) -> None:
        """Release auto-endpoint patches (refcounted)."""
        with self._lock:
            if self._count == 0:
                return
            self._count -= 1
            if self._count > 0:
                return
            self._restore_s3fs()
            self._restore_aiobotocore()
            self._restore_botocore()
            self._endpoint = None
            self._mode = None

    def _patch_botocore(self) -> None:
        if self._original_botocore_create is not None:
            return
        self._original_botocore_create = BotocoreSession.create_client
        original_create_client = self._original_botocore_create
        signature = inspect.signature(original_create_client)

        def _create_client(
            session_self: BotocoreSession, *args: Any, **kwargs: Any
        ) -> Any:
            bound = signature.bind(session_self, *args, **kwargs)
            bound.apply_defaults()
            if self._endpoint is None or self._mode is None:
                raise RuntimeError("aiomoto server_mode auto-endpoint not configured.")
            _apply_client_defaults(bound.arguments, self._endpoint, self._mode)
            return original_create_client(*bound.args, **bound.kwargs)

        method_name = "create_client"
        setattr(BotocoreSession, method_name, _create_client)

    def _restore_botocore(self) -> None:
        if self._original_botocore_create is not None:
            method_name = "create_client"
            setattr(BotocoreSession, method_name, self._original_botocore_create)
            self._original_botocore_create = None

    def _patch_aiobotocore(self) -> None:
        if self._original_aio_create is not None:
            return
        if importlib.util.find_spec("aiobotocore.session") is None:
            return
        from aiobotocore.session import AioSession

        method_name = "_create_client"
        self._original_aio_create = getattr(AioSession, method_name)
        original_create_client = self._original_aio_create
        signature = inspect.signature(original_create_client)

        async def _create_client(
            session_self: AioSession, *args: Any, **kwargs: Any
        ) -> Any:
            bound = signature.bind(session_self, *args, **kwargs)
            bound.apply_defaults()
            if self._endpoint is None or self._mode is None:
                raise RuntimeError("aiomoto server_mode auto-endpoint not configured.")
            _apply_client_defaults(bound.arguments, self._endpoint, self._mode)
            return await original_create_client(*bound.args, **bound.kwargs)

        method_name = "_create_client"
        setattr(AioSession, method_name, _create_client)

    def _restore_aiobotocore(self) -> None:
        if self._original_aio_create is None:
            return
        from aiobotocore.session import AioSession

        method_name = "_create_client"
        setattr(AioSession, method_name, self._original_aio_create)
        self._original_aio_create = None

    def _patch_s3fs(self) -> None:
        if self._original_s3fs_init is not None:
            return
        if importlib.util.find_spec("s3fs") is None:
            return
        from s3fs.core import S3FileSystem

        self._original_s3fs_init = S3FileSystem.__init__
        original_init = self._original_s3fs_init
        signature = inspect.signature(original_init)

        def _init(fs_self: S3FileSystem, *args: Any, **kwargs: Any) -> None:
            bound = signature.bind(fs_self, *args, **kwargs)
            bound.apply_defaults()
            endpoint_url = bound.arguments.get("endpoint_url")
            client_kwargs = bound.arguments.get("client_kwargs")
            config_kwargs = bound.arguments.get("config_kwargs")
            if (
                self._endpoint is not None
                and self._mode is not None
                and client_kwargs is None
                and config_kwargs is None
                and _should_inject(self._mode, endpoint_url)
            ):
                bound.arguments["endpoint_url"] = self._endpoint
                bound.arguments["use_ssl"] = False
                access_key, secret_key, token = _default_creds()
                bound.arguments["client_kwargs"] = {
                    "aws_access_key_id": access_key,
                    "aws_secret_access_key": secret_key,
                    "aws_session_token": token,
                    "region_name": _default_region(),
                }
                bound.arguments["config_kwargs"] = {"s3": {"addressing_style": "path"}}
            return original_init(*bound.args, **bound.kwargs)

        method_name = "__init__"
        setattr(S3FileSystem, method_name, _init)

    def _restore_s3fs(self) -> None:
        if self._original_s3fs_init is None:
            return
        from s3fs.core import S3FileSystem

        method_name = "__init__"
        setattr(S3FileSystem, method_name, self._original_s3fs_init)
        self._original_s3fs_init = None
