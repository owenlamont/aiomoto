"""Patch registry exports."""

from aiomoto.patches.aioboto3 import Aioboto3Patcher
from aiomoto.patches.core import CorePatcher


__all__ = ["Aioboto3Patcher", "CorePatcher"]
