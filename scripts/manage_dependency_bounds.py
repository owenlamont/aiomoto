"""Manage bounds for key async AWS dependencies in pyproject.toml.

Workflow semantics:
  - loosen-bounds:
      * Record current lower/upper bounds to artifacts/bounds_snapshot.json.
      * Promote the existing upper bound to be the new lower bound.
      * Drop any upper bound so the workflow only explores versions >= old upper.
  - add-bounds:
      * Load the snapshot to restore the original lower bound.
      * Read the installed versions from the environment.
      * Set a new upper bound that is monotonic: max(previous upper, next major
        of installed version). Keeps lower bound at the original value.
"""

import argparse
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from packaging.requirements import Requirement
from packaging.specifiers import Specifier
from packaging.version import Version
import tomlkit


@dataclass(frozen=True)
class Bound:
    token: str  # e.g., "aiobotocore" or "moto[s3]"
    upper: str  # e.g., "<3.0.0"

    @property
    def base(self) -> str:
        """Return base package name without extras."""
        return self.token.split("[", 1)[0]


# Bounds we actively manage (aioboto3-related dev deps and stub packages are
# intentionally excluded).
BOUNDS: tuple[Bound, ...] = (
    Bound("aiobotocore", "<=2.25.2"),
    Bound("moto", "<=5.1.17"),
    Bound("moto[", "<=5.1.17"),  # handles moto extras (prefix match)
)
SNAPSHOT_PATH = Path("artifacts/bounds_snapshot.json")


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments.

    Returns:
        Parsed argparse namespace.
    """

    parser = argparse.ArgumentParser(
        description="Loosen or restore dependency upper bounds in pyproject.toml"
    )
    parser.add_argument(
        "command", choices=["loosen-bounds", "add-bounds"], help="Operation to run"
    )
    parser.add_argument(
        "--project-path", default="pyproject.toml", help="Path to pyproject.toml"
    )
    return parser.parse_args()


def is_match(value: str, bound: Bound) -> bool:
    """Return True if the dependency string targets the given bound token."""

    req = Requirement(value)
    if bound.token.endswith("["):  # moto extras wildcard
        return req.name == bound.base
    return req.name == bound.base


def extract_bounds(req: Requirement) -> tuple[str | None, str | None]:
    """Return lower and upper (inclusive) from a parsed requirement."""

    lower = None
    upper = None
    for spec in req.specifier:
        if spec.operator == ">=":
            lower = spec.version
        elif spec.operator == "<=":
            upper = spec.version
        elif spec.operator == "<":
            upper = spec.version  # treat non-inclusive as upper candidate
    return lower, upper


def render_req(req: Requirement, specs: list[Specifier]) -> str:
    """Render a Requirement with a new specifier list, keeping extras/markers.

    Returns:
        Canonicalized requirement string with updated specifiers.
    """

    base = req.name
    if req.extras:
        base = f"{base}[{','.join(sorted(req.extras))}]"
    spec_text = ",".join(str(s) for s in specs) if specs else ""
    marker_text = f"; {req.marker}" if req.marker else ""
    return f"{base}{spec_text}{marker_text}"


def loosen_item(value: str, bound: Bound) -> tuple[str, dict[str, str]]:
    """Promote existing upper bound to lower and drop upper.

    Returns:
        Updated dependency string and captured bounds snapshot (possibly empty).
    """

    if not is_match(value, bound):
        return value, {}

    req = Requirement(value)
    lower, upper = extract_bounds(req)

    snapshot: dict[str, str] = {}
    if lower:
        snapshot["lower"] = lower
    if upper:
        snapshot["upper"] = upper

    # If there was an upper bound, promote it to the new lower bound.
    if upper:
        lower = upper

    specs: list[Specifier] = []
    if lower:
        specs.append(Specifier(f">={lower}"))

    return render_req(req, specs), snapshot


def add_bound_item(
    value: str,
    bound: Bound,
    snapshot: dict[str, dict[str, str]],
    resolved: dict[str, str],
) -> str:
    """Restore lower bound and set a monotonic upper bound based on resolved versions.

    Returns:
        Updated dependency string.
    """

    if not is_match(value, bound):
        return value

    req = Requirement(value)
    base = req.name
    snap = snapshot.get(base) or {}
    lower = snap.get("lower")
    previous_upper = snap.get("upper")

    installed = resolved.get(base)
    new_upper = previous_upper
    if installed and ((not new_upper) or (Version(installed) > Version(new_upper))):
        new_upper = installed

    specs: list[Specifier] = []
    if lower:
        specs.append(Specifier(f">={lower}"))
    if new_upper:
        specs.append(Specifier(f"<={new_upper}"))

    return render_req(req, specs)


def apply(
    doc: tomlkit.TOMLDocument,
    fn,
    snapshot: dict[str, dict[str, str]] | None = None,
    resolved: dict[str, str] | None = None,
) -> dict[str, dict[str, str]]:
    """Apply a transform function to relevant dependency arrays.

    Returns:
        Snapshot of original bounds (for loosen) when produced, otherwise the
        incoming snapshot.
    """

    sections = collect_sections(doc)
    produced: dict[str, dict[str, str]] = snapshot or {}

    for arr in sections:
        _process_section(arr, fn, produced, resolved or {})

    return produced


def collect_sections(doc: tomlkit.TOMLDocument) -> list[Iterable[str]]:
    """Collect dependency arrays from project/optional/dep-groups.

    Returns:
        List of dependency arrays to mutate.
    """

    sections: list[Iterable[str]] = []
    project = doc.get("project", {})
    sections.append(project.get("dependencies", []))

    optional = project.get("optional-dependencies", {})
    sections.extend(optional.values())

    dep_groups = doc.get("dependency-groups", {})
    sections.extend(dep_groups.values())
    return sections


def _process_section(
    arr: Iterable[str],
    fn,
    produced: dict[str, dict[str, str]],
    resolved: dict[str, str],
) -> None:
    """Process a single dependency array."""

    for idx, val in enumerate(list(arr)):
        for bound in BOUNDS:
            if fn is loosen_item:
                new_val, snap = fn(val, bound)
                if snap:
                    produced.setdefault(bound.base, {}).update(snap)
            else:
                new_val = fn(val, bound, produced, resolved)
            if new_val != val:
                arr[idx] = new_val
                val = new_val  # so further bounds see updated string


def load_snapshot() -> dict[str, dict[str, str]]:
    """Load the bounds snapshot if it exists.

    Returns:
        Snapshot mapping base package -> {lower, upper}.
    """

    if SNAPSHOT_PATH.exists():
        import json

        return json.loads(SNAPSHOT_PATH.read_text())
    return {}


def save_snapshot(data: dict[str, dict[str, str]]) -> None:
    """Persist the bounds snapshot."""

    if not data:
        return
    SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
    import json

    SNAPSHOT_PATH.write_text(json.dumps(data, indent=2))


def resolve_versions() -> dict[str, str]:
    """Return installed versions for the bound packages."""

    resolved: dict[str, str] = {}
    for bound in BOUNDS:
        base = bound.base
        if base in resolved:
            continue
        try:
            from importlib.metadata import version

            resolved[base] = version(base)
        except Exception as exc:
            # Non-fatal: package might not be installed in the workflow env.
            print(
                f"[manage-bounds] Warning: could not resolve version for {base}: {exc}"
            )
            continue
    return resolved


def main() -> None:
    """CLI entrypoint.

    Raises:
        SystemExit: if add-bounds is invoked without a prior loosen snapshot.
    """

    args = parse_args()
    path = Path(args.project_path)
    doc = tomlkit.parse(path.read_text())

    if args.command == "loosen-bounds":
        snapshot = apply(doc, loosen_item)
        save_snapshot(snapshot)
    else:  # add-bounds
        snapshot = load_snapshot()
        if not snapshot:
            raise SystemExit(
                "bounds snapshot missing; run loosen-bounds before add-bounds"
            )
        resolved = resolve_versions()
        apply(doc, add_bound_item, snapshot=snapshot, resolved=resolved)
        if SNAPSHOT_PATH.exists():
            SNAPSHOT_PATH.unlink()

    path.write_text(tomlkit.dumps(doc))


if __name__ == "__main__":
    main()
