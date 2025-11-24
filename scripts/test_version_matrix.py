"""Run a bounded matrix of aiobotocore/moto versions against a test subset.

Usage examples:
    uv run python scripts/test_version_matrix.py
    uv run python scripts/test_version_matrix.py --aiobotocore 2.25.2 2.24.3 \
        --moto 5.1.17 5.1.13 --tests tests/test_s3_async.py

The script installs each version pair into the current environment (using uv pip
install --upgrade) and runs the selected tests. Results are printed and written
to JSON so we can pick safe minimum bounds for pyproject.toml.
"""

import argparse
import json
from pathlib import Path
import subprocess  # noqa: S404
import time
from typing import Any


DEFAULT_AIOBOTOCORE = ["2.25.2", "2.24.3", "2.24.1"]
DEFAULT_MOTO = ["5.1.17", "5.1.13", "5.1.5"]
DEFAULT_TESTS = [
    "tests/test_s3_async.py",
    "tests/test_dynamodb_async.py",
    "tests/test_secretsmanager_async.py",
    "tests/test_ses_async.py",
    "tests/test_smoke.py",
]
RESULTS_PATH = Path("artifacts/version-matrix.json")


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    """Run a command and return the completed process.

    Returns:
        Completed process with stdout/stderr captured.
    """

    return subprocess.run(cmd, text=True, capture_output=True, check=False)  # noqa: S603


def run_combo(aio_ver: str, moto_ver: str, tests: list[str]) -> dict[str, Any]:
    """Install the version pair and execute pytest.

    Returns:
        Mapping with status, returncode, stdout/stderr, and duration.
    """

    result: dict[str, Any] = {
        "aiobotocore": aio_ver,
        "moto": moto_ver,
        "status": "pending",
        "duration_s": None,
        "stdout": "",
        "stderr": "",
        "returncode": None,
    }

    install = run(
        [
            "uv",
            "pip",
            "install",
            "--upgrade",
            f"aiobotocore=={aio_ver}",
            f"moto=={moto_ver}",
        ]
    )
    if install.returncode != 0:
        result.update(
            {
                "status": "install-failed",
                "returncode": install.returncode,
                "stdout": install.stdout,
                "stderr": install.stderr,
            }
        )
        return result

    start = time.perf_counter()
    test_proc = run(["uv", "run", "pytest", *tests])
    duration = time.perf_counter() - start

    result.update(
        {
            "status": "passed" if test_proc.returncode == 0 else "failed",
            "returncode": test_proc.returncode,
            "duration_s": round(duration, 2),
            "stdout": test_proc.stdout,
            "stderr": test_proc.stderr,
        }
    )
    return result


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments.

    Returns:
        Parsed argparse namespace.
    """

    parser = argparse.ArgumentParser(description="Test version matrix for aiomoto.")
    parser.add_argument(
        "--aiobotocore",
        nargs="+",
        default=DEFAULT_AIOBOTOCORE,
        help="aiobotocore versions to try (latest first)",
    )
    parser.add_argument(
        "--moto",
        nargs="+",
        default=DEFAULT_MOTO,
        help="moto versions to try (latest first)",
    )
    parser.add_argument(
        "--tests",
        nargs="+",
        default=DEFAULT_TESTS,
        help="Pytest targets to run for each combo",
    )
    parser.add_argument(
        "--output", type=Path, default=RESULTS_PATH, help="Path to write JSON results"
    )
    return parser.parse_args()


def main() -> None:
    """CLI entrypoint."""

    args = parse_args()
    results: list[dict[str, Any]] = []

    args.output.parent.mkdir(parents=True, exist_ok=True)

    for moto_ver in args.moto:
        for aio_ver in args.aiobotocore:
            print(f"=== moto {moto_ver} / aiobotocore {aio_ver} ===")
            res = run_combo(aio_ver, moto_ver, args.tests)
            results.append(res)
            print(
                f"status: {res['status']} (rc={res['returncode']}) "
                f"dur={res['duration_s']}"
            )
            if res["status"] != "passed":
                # Stop descending for this moto version when aiobotocore fails.
                break

    args.output.write_text(json.dumps(results, indent=2))
    print(f"\nSaved results to {args.output}")


if __name__ == "__main__":
    main()
