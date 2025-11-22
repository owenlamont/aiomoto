from __future__ import annotations

from typing import Any

import aioboto3
from boto3.exceptions import ResourceNotExistsError, UnknownAPIVersionError
from boto3.session import DataNotFoundError, UnknownServiceError
import pytest

from aiomoto.patches.aioboto3 import (
    Aioboto3Patcher,
    patch_aioboto3_resource,
    restore_aioboto3_resource,
)


def test_aioboto3_patcher_idempotent() -> None:
    patcher = Aioboto3Patcher(aioboto3.session)
    patcher.start()
    patcher.start()
    patcher.stop()
    patcher.stop()


def test_aioboto3_resource_errors_and_restore_noop() -> None:
    class Loader:
        def load_service_model(
            self, service_name: str, model: str, api_version: str | None
        ) -> Any:
            if service_name == "missing":
                raise UnknownServiceError(
                    service_name=service_name, known_service_names=["s3"]
                )
            raise DataNotFoundError(data_path="resources-1")

        def list_api_versions(self, service_name: str, model: str) -> list[str]:
            return ["v1"]

    class SessionMod:
        class Session:
            def resource(self, *_args: Any, **_kwargs: Any) -> Any:
                return None

            _loader = Loader()

            def get_available_resources(self) -> list[str]:
                return ["s3"]

            def get_available_services(self) -> list[str]:
                return ["s3"]

    # Hit the original stub before it gets replaced
    assert SessionMod.Session().resource("noop") is None

    patch_aioboto3_resource(SessionMod)
    with pytest.raises(ResourceNotExistsError):
        SessionMod.Session().resource("missing")

    with pytest.raises(UnknownAPIVersionError):
        SessionMod.Session().resource("other")

    restore_aioboto3_resource(SessionMod)
