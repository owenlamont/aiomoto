"""aioboto3 resource patch to support async clients."""

from __future__ import annotations

from types import TracebackType
from typing import Any

import boto3
from boto3.exceptions import ResourceNotExistsError, UnknownAPIVersionError
from boto3.session import DataNotFoundError, UnknownServiceError
from botocore.config import Config


class ResourceCreatorContext:
    """Async context building a service resource from an async aioboto3 client."""

    def __init__(
        self,
        session: Any,
        service_name: str,
        region_name: str | None,
        api_version: str | None,
        use_ssl: bool,
        verify: bool | str | None,
        endpoint_url: str | None,
        aws_access_key_id: str | None,
        aws_secret_access_key: str | None,
        aws_session_token: str | None,
        config: Config,
        resource_model: dict[str, Any],
    ) -> None:
        self.service_name = service_name
        self.resource_model = resource_model
        self.session = session
        self.api_version = api_version
        self.cls: Any | None = None
        self.client_ctx = session.client(
            service_name,
            region_name=region_name,
            api_version=api_version,
            use_ssl=use_ssl,
            verify=verify,
            endpoint_url=endpoint_url,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            aws_session_token=aws_session_token,
            config=config,
        )

    async def __aenter__(self) -> Any:
        client = await self.client_ctx.__aenter__()
        service_model = client.meta.service_model
        service_context = boto3.utils.ServiceContext(
            service_name=self.service_name,
            service_model=service_model,
            resource_json_definitions=self.resource_model["resources"],
            service_waiter_model=None,
        )

        # Avoid async emitter issues inside the factory by using a no-op emitter.
        factory = self.session.resource_factory
        original_emitter = getattr(factory, "_emitter", None)

        class _SyncEmitter:
            def emit(self, *args: Any, **kwargs: Any) -> list[Any]:
                return []

            def emit_until_response(
                self, *args: Any, **kwargs: Any
            ) -> tuple[Any | None, Any | None]:
                return None, None

        factory._emitter = _SyncEmitter()
        resource_cls = factory.load_from_definition(
            resource_name=self.service_name,
            single_resource_json_definition=self.resource_model["service"],
            service_context=service_context,
        )
        factory._emitter = original_emitter

        self.cls = resource_cls(client=client)

        return self.cls

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.client_ctx.__aexit__(exc_type, exc, tb)
        self.cls = None


def patch_aioboto3_resource(session_mod: Any) -> None:
    """Replace aioboto3 Session.resource with async-aware version."""

    orig = session_mod.Session.resource

    def resource(
        self: Any,
        service_name: str,
        region_name: str | None = None,
        api_version: str | None = None,
        use_ssl: bool = True,
        verify: bool | str | None = None,
        endpoint_url: str | None = None,
        aws_access_key_id: str | None = None,
        aws_secret_access_key: str | None = None,
        aws_session_token: str | None = None,
        config: Config | None = None,
    ) -> ResourceCreatorContext:
        try:
            resource_model = self._loader.load_service_model(
                service_name, "resources-1", api_version
            )
        except UnknownServiceError:
            available = self.get_available_resources()
            has_low_level_client = service_name in self.get_available_services()
            raise ResourceNotExistsError(
                service_name, available, has_low_level_client
            ) from None
        except DataNotFoundError:
            available_api_versions = self._loader.list_api_versions(
                service_name, "resources-1"
            )
            raise UnknownAPIVersionError(
                service_name, api_version or "", ", ".join(available_api_versions)
            ) from None

        if api_version is None:
            api_version = self._loader.determine_latest_version(
                service_name, "resources-1"
            )

        if config is None:
            config = Config(user_agent_extra="Resource")

        return ResourceCreatorContext(
            self,
            service_name,
            region_name,
            api_version,
            use_ssl,
            verify,
            endpoint_url,
            aws_access_key_id,
            aws_secret_access_key,
            aws_session_token,
            config,
            resource_model,
        )

    session_mod.Session.resource = resource
    session_mod.Session._aiomoto_resource_orig = orig


def restore_aioboto3_resource(session_mod: Any) -> None:
    """Restore aioboto3 Session.resource if aiomoto patched it."""

    orig = getattr(session_mod.Session, "_aiomoto_resource_orig", None)
    if orig is not None:
        session_mod.Session.resource = orig
