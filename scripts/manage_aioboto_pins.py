# Adjust aioboto3/aiobotocore pins for upgrade workflows.

import argparse
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
import shutil
import subprocess  # noqa: S404
import sys

import tomlkit


PINNED_PACKAGES = (
    ("aiobotocore", None),
    ("aioboto3", None),
    ("types-aiobotocore", "[full]"),
    ("types-aioboto3", "[full]"),
)


@dataclass
class Replacement:
    """Value object describing a single dependency pin replacement."""

    name: str
    extras: str | None
    operator: str
    version: str

    @property
    def token(self) -> str:
        """Return canonical package token including extras if present.

        Returns:
            Token string such as ``aioboto3`` or ``types-aioboto3[full]``.
        """

        return f"{self.name}{self.extras or ''}"

    def render(self) -> str:
        """Render the dependency constraint string.

        Returns:
            Fully rendered pin like ``aioboto3==15.5.0``.
        """

        return f"{self.token}{self.operator}{self.version}"


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for the pin manager script.

    Returns:
        Parsed arguments from the command line.
    """

    parser = argparse.ArgumentParser(
        description="Manage aioboto pins in pyproject.toml"
    )
    parser.add_argument(
        "command", choices=["loosen", "repin"], help="Operation to perform"
    )
    parser.add_argument(
        "--project-path", default="pyproject.toml", help="Path to pyproject.toml"
    )
    return parser.parse_args()


def discover_existing_version(value: str, token: str) -> str | None:
    """Extract the pinned version from a dependency string if present.

    Returns:
        Version string if found, otherwise ``None``.
    """

    for operator in ("==", ">="):
        marker = f"{token}{operator}"
        if value.startswith(marker):
            return value.removeprefix(marker)
    return None


def split_dependency(value: str) -> tuple[str, str | None, str | None]:
    """Split a dependency string into token/operator/version components.

    Returns:
        Tuple of token, operator (``==``/``>=``/``None``), and version (or ``None``).
    """

    for operator in ("==", ">="):
        if operator in value:
            before, after = value.split(operator, 1)
            return before, operator, after
    return value, None, None


def split_token(token: str) -> tuple[str, str | None]:
    """Split a token into package name and extras.

    Returns:
        Tuple of package name and extras string (including brackets) or ``None``.
    """

    if "[" in token:
        name, rest = token.split("[", 1)
        return name, f"[{rest}"
    return token, None


def base_name(token: str) -> str:
    """Return the package name without extras."""

    return split_token(token)[0]


def is_moto_token(token: str) -> bool:
    """Return True when the dependency token refers to moto or a moto extra."""

    return token.startswith("moto")


def loosening_replacement(value: str) -> Replacement | None:
    """Return a relaxed replacement for a dependency string, if applicable."""

    token, _operator, version = split_dependency(value)
    if not version:
        return None

    if token in {f"{name}{extras or ''}" for name, extras in PINNED_PACKAGES}:
        name, extras = split_token(token)
        return Replacement(name, extras, ">=", version)

    if is_moto_token(token):
        name, extras = split_token(token)
        return Replacement(name, extras, ">=", version)

    if token.startswith("boto3-stubs"):
        return Replacement("boto3-stubs", "[full]", ">=", version)

    return None


def repin_replacement(token: str, versions: dict[str, str]) -> Replacement | None:
    """Return a strict replacement for a dependency string, if applicable."""

    base = base_name(token)
    pinned_tokens = {f"{name}{extras or ''}" for name, extras in PINNED_PACKAGES}

    if token in pinned_tokens or base in {
        "aiobotocore",
        "aioboto3",
        "types-aiobotocore",
        "types-aioboto3",
    }:
        version = versions.get(base)
        if version:
            name, extras = split_token(token)
            return Replacement(name, extras, "==", version)

    if is_moto_token(token):
        version = versions.get("moto")
        if version:
            name, extras = split_token(token)
            return Replacement(name, extras, "==", version)

    if token.startswith("boto3-stubs"):
        version = versions.get("boto3") or versions.get("boto3-stubs")
        if version:
            return Replacement("boto3-stubs", "[full]", "==", version)

    return None


def apply_replacements(
    array: tomlkit.items.Array, replacements: Iterable[Replacement]
) -> None:
    """Apply replacements in-place to a TOML array of dependency strings."""

    ordered = sorted(replacements, key=lambda r: len(r.token), reverse=True)
    for idx, item in enumerate(array):
        if not isinstance(item, str):
            continue
        base = base_name(item)
        for replacement in ordered:
            if replacement.name == "boto3-stubs":
                match = item.startswith(replacement.token) or base == replacement.name
            elif replacement.extras:
                match = item.startswith(replacement.token)
            else:
                match = item.startswith(replacement.token) or base == replacement.name

            if match:
                array[idx] = replacement.render()
                break


def build_loosen_replacements(doc: tomlkit.TOMLDocument) -> list[Replacement]:
    """Build replacement list converting strict pins to minimum versions.

    Returns:
        Replacement objects that relax aioboto pins.
    """

    replacements: list[Replacement] = []
    project_deps = list(doc["project"].get("dependencies", []))
    optional = doc["project"].get("optional-dependencies", {})
    dep_groups = doc.get("dependency-groups", {})

    def maybe_add_from_array(arr: Iterable[str]) -> None:
        for value in arr:
            replacement = loosening_replacement(value)
            if replacement:
                replacements.append(replacement)

    maybe_add_from_array(project_deps)
    for arr in optional.values():
        maybe_add_from_array(arr)
    for arr in dep_groups.values():
        maybe_add_from_array(arr)
    return replacements


def build_repin_replacements(
    doc: tomlkit.TOMLDocument, versions: dict[str, str]
) -> list[Replacement]:
    """Build replacement list pinning to versions resolved in the env.

    Raises:
        SystemExit: If a required package is missing from the environment.

    Returns:
        Replacement objects that restore strict pins.
    """

    replacements: list[Replacement] = []
    project_deps = list(doc["project"].get("dependencies", []))
    optional = doc["project"].get("optional-dependencies", {})
    dep_groups = doc.get("dependency-groups", {})

    def maybe_add_from_array(arr: Iterable[str]) -> None:
        for value in arr:
            token, _operator, _version = split_dependency(value)
            replacement = repin_replacement(token, versions)
            if replacement:
                replacements.append(replacement)

    maybe_add_from_array(project_deps)
    for arr in optional.values():
        maybe_add_from_array(arr)
    for arr in dep_groups.values():
        maybe_add_from_array(arr)

    if not replacements:
        raise SystemExit("Package versions not found in environment")

    return replacements


def current_versions() -> dict[str, str]:
    """Read resolved versions from the active environment via pip show.

    Returns:
        Mapping of package name to resolved version.

    Raises:
        SystemExit: If the pip invocation fails or returns no data.
    """

    targets = [
        "aiobotocore",
        "aioboto3",
        "types-aiobotocore",
        "types-aioboto3",
        "moto",
        "boto3",
        "boto3-stubs",
    ]

    def run_pip_show(cmd: list[str]) -> dict[str, str]:
        result = subprocess.run(  # noqa: S603
            cmd, check=False, text=True, capture_output=True
        )
        if result.returncode != 0:
            return {}
        versions: dict[str, str] = {}
        current_name: str | None = None
        for line in result.stdout.splitlines():
            if line.startswith("Name:"):
                current_name = line.split(":", 1)[1].strip()
                continue
            if line.startswith("Version:") and current_name:
                versions[current_name] = line.split(":", 1)[1].strip()
        return versions

    # Prefer the interpreter this script is running under (uv run uses project venv).
    versions = run_pip_show([sys.executable, "-m", "pip", "show", *targets])
    if versions:
        return versions

    uv_exe = shutil.which("uv") or "uv"
    versions = run_pip_show([uv_exe, "pip", "show", *targets])
    if versions:
        return versions

    raise SystemExit("Unable to determine versions via pip show")


def mutate_pyproject(
    doc: tomlkit.TOMLDocument, replacements: Iterable[Replacement]
) -> tomlkit.TOMLDocument:
    """Apply replacements across project, optional, and dependency groups.

    Returns:
        Mutated TOML document with updated dependency strings.
    """

    project = doc["project"]
    deps = project.get("dependencies")
    if isinstance(deps, tomlkit.items.Array):
        apply_replacements(deps, replacements)

    optional = project.get("optional-dependencies", {})
    for arr in optional.values():
        if isinstance(arr, tomlkit.items.Array):
            apply_replacements(arr, replacements)

    dep_groups = doc.get("dependency-groups", {})
    for arr in dep_groups.values():
        if isinstance(arr, tomlkit.items.Array):
            apply_replacements(arr, replacements)
    return doc


def main() -> None:
    """CLI entrypoint for the pin manager script.

    Raises:
        SystemExit: If no matching dependencies are found to update.
    """

    args = parse_args()
    project_path = Path(args.project_path)
    doc = tomlkit.parse(project_path.read_text())

    if args.command == "loosen":
        replacements = build_loosen_replacements(doc)
    else:
        versions = current_versions()
        replacements = build_repin_replacements(doc, versions)

    if not replacements:
        raise SystemExit("No matching dependencies found to update")

    mutated = mutate_pyproject(doc, replacements)
    project_path.write_text(tomlkit.dumps(mutated))


if __name__ == "__main__":
    main()
