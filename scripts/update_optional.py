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


path = Path("pyproject.toml")
doc = tomlkit.parse(path.read_text())
project = doc["project"]
optional = project.setdefault("optional-dependencies", tomlkit.table())
extras = sorted(metadata.metadata("moto").get_all("Provides-Extra") or [])
version = metadata.version("moto")
for extra in extras:
    arr = tomlkit.array().multiline(False)
    arr.append(f"moto[{extra}]=={version}")
    optional[extra] = arr
path.write_text(tomlkit.dumps(doc))
