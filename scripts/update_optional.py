# This helper regenerates aiomoto's optional dependency groups so they stay in sync
# with the extras exposed by moto. Run `uv run --with moto==<version>
# scripts/update_optional.py` whenever moto releases a new version.
#
# /// script
# requires-python = ">=3.11"
# dependencies = ["tomlkit"]
# ///
from importlib import metadata
from pathlib import Path

import tomlkit
from tomlkit.items import Table


path = Path("pyproject.toml")
doc = tomlkit.parse(path.read_text())
project = doc.get("project")
if not isinstance(project, Table):
    raise ValueError("Expected [project] table in pyproject.toml")

optional = project.get("optional-dependencies")
if optional is None:
    optional = tomlkit.table()
    project["optional-dependencies"] = optional
elif not isinstance(optional, Table):
    raise ValueError("Expected [project.optional-dependencies] to be a table")
extras = sorted(metadata.metadata("moto").get_all("Provides-Extra") or [])
version = metadata.version("moto")
for extra in extras:
    arr = tomlkit.array().multiline(False)
    arr.append(f"moto[{extra}]=={version}")
    optional[extra] = arr
path.write_text(tomlkit.dumps(doc))
