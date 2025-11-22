# Coding Agent Instructions

Guidance on how to navigate and modify this codebase.

## What This Library Does

aiomoto is an installable Python package that brings Moto-style AWS service mocks to
async stacks such as aioboto3 or aiobotocore while staying compatible with classic
boto3. The focus is a clean, reusable library API rather than a CLI entry point.

## Code Change Requirements

- Whenever code is changed, ensure all pre-commit linters pass (`prek run --all-files`)
  and all pytests pass (`uv run pytest`). Newly added code must keep full branch
  coverage. Always invoke these commands with a multi-minute timeout (>= 4 minutes)
  and, when using sandboxed Codex tooling, request elevated permissions each time so
  the commands can access the full workspace and any required local services. In
  unrestricted environments just make sure the resources are reachable.
- When running ad-hoc Python (inspecting objects, small scripts, etc.), use
  `uv run python` so the project venv and pinned dependencies are active.
- Update documentation whenever behaviour or feature changes are introduced.

## Project Structure

- **/src/aiomoto/** – Library code.
- **/tests/** – Pytest suite kept in sync with the src layout; module names mirror
  the src module they cover and use the `test_` prefix.
- **Wiki** – <https://github.com/owenlamont/aiomoto/wiki> (roadmap, etc.). Keep wiki
  pages in sync when behaviour changes.
- **.complexipy.toml** – Complexipy configuration.
- **.coveragerc** – Coverage path mappings.
- **mypy.ini** – MyPy type checker configuration.
- **pyproject.toml** – Package configuration (distribution metadata, optional
  extras, build backend, and dependency groups).
- **.pre-commit-config.yaml** – Pre-commit linters and configuration.
- **pytest.ini** – Pytest configuration.
- **ruff.toml** – Code style and linter configuration.
- **.rumdl.toml** – Markdown linter configuration.
- **.yamllint** – YAML linter configuration.
- **typos.toml** – Typos configuration.

## Code Style

- Run `prek run --all-files` after every meaningful edit so auto-fixes keep the
  working tree clean; this applies even to documentation-only edits because Markdown
  linting runs through prek.
- Stage any new files before running prek so they are included in the checks.
- Let prek auto-correct formatting issues where possible. If prek reports changes,
  rerun it to confirm a clean pass before fixing anything manually.
- Follow the [Google Python Style Guide]
  (<https://google.github.io/styleguide/pyguide.html>) for all code contributions,
  including Google-style docstrings.
- Use precise type hints everywhere. Avoid `Any`, type casts, and type ignores unless
  a third-party dependency leaves no alternative.
- Do not create sub-packages inside `tests`. Test module names must be unique across
  the repo (other than `__init__.py` and `conftest.py`).
- Use the most modern Python idioms allowed by the minimum supported version
  (currently Python 3.14). Once support broadens, remember to update the workflows
  alongside the code.
- Prefer readable names over comments. Docstrings belong on public functions when the
  signature alone is not clear. Comments should be saved for unavoidable code smells,
  temporary pins (with links), or opaque logic.
- Keep imports at the top of modules unless a circular import would result.
- Prefer quick research (docs or web search) to validate tools/APIs before
  trial-and-error patches; it is usually faster and reduces churn.

## Development Environment / Terminal

- The repo runs on macOS, Linux, and Windows. Confirm the shell environment before
  assuming POSIX semantics.
- When automation already controls the working directory, run commands directly (for
  example `prek run --all-files`) instead of prefixing them with `cd`.
- Being a uv project you never need to activate a virtual environment or call pip
  directly. Use `uv add` for dependencies and `uv run` for scripts or tooling.
- Install `complexipy`, `markitdown`, `prek`, `rg`, `ruff`, `rumdl`, `typos`, and
  `zizmor` as global uv tools so they can be invoked without `uv run`.

## Automated Tests

- Always run `uv run pytest` when fixing bugs or making incremental code changes.
- For new features or larger changes run `uv run pytest --cov=. --cov-branch
  --cov-report term-missing` and inspect any uncovered lines. Some conditional logic
  is platform- or version-specific, so 100% branch coverage may require CI, but treat
  any gaps as suspect until proven otherwise.
- Future integration tests may rely on AWS emulators such as DynamoDB Local on
  `http://localhost:8000`. Request elevated permissions when needed so those
  endpoints remain reachable.
- Tests treat warnings as errors. Fix warnings raised by this repo. Third-party
  warnings can be explicitly ignored when necessary.
- Only use test functions (no classes). Put setup into fixtures or parameters so the
  code under test is near the top of each function.
- Use explicit `pytest.param` entries with meaningful `id` strings for parametrized
  tests.
- Skip test docstrings and comments; describe intent through descriptive names and
  param ids.
- Each new test should meaningfully increase coverage. Aim for full branch coverage
  while keeping the ratio of test code to src code lean.
