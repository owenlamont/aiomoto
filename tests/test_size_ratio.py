from __future__ import annotations

import os
from pathlib import Path


MAX_RATIO = float(os.getenv("AIOMOTO_MAX_TEST_RATIO", "0.9"))


def _total_bytes(root: Path) -> int:
    return sum(path.stat().st_size for path in root.rglob("*.py"))


def test_test_to_src_size_ratio_is_reasonable() -> None:
    """Guardrail: keep tests from ballooning relative to src."""

    src_bytes = _total_bytes(Path(__file__).parent.parent / "src")
    test_bytes = _total_bytes(Path(__file__).parent)

    assert src_bytes > 0, "src should not be empty"

    ratio = test_bytes / src_bytes
    assert ratio <= MAX_RATIO, (
        f"tests/src size ratio {ratio:.3f} exceeds limit {MAX_RATIO:.3f}. "
        "Refactor tests or raise AIOMOTO_MAX_TEST_RATIO intentionally."
    )
