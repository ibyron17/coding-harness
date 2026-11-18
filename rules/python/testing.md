---
paths:
  - "**/*.py"
  - "**/*.pyi"
---
# Python Testing

> This file extends [common/testing.md](../common/testing.md) with Python specific content.

## Framework

Use the test framework the project already uses — don't convert existing tests or add a second runner.

- **pytest** — `[tool.pytest.ini_options]` in `pyproject.toml`, a `pytest.ini`, a `conftest.py`, or
  pytest in the dev dependencies.
- **unittest** — test classes subclass `unittest.TestCase` and no pytest configuration exists.

A project with no tests yet: default to **pytest**, and record the choice in the project's
`CLAUDE.md` so later sessions don't decide it again.

## Running

Run through the project's environment manager so the pinned dependencies are used — `uv run …` when
`uv.lock` exists, `poetry run …` when `poetry.lock` exists, otherwise `python -m …` (`python -m pytest`,
`python -m unittest discover -s <dir> -t <root>`). Narrow to the affected path first, then run the
whole suite.

## Async Tests

Follow the async plugin and mode the configuration already sets (e.g. pytest-asyncio's
`asyncio_mode`); don't add event-loop fixtures the configuration already provides.

## Isolation

- Replace the narrowest seam — an attribute of the module under test (pytest `monkeypatch`,
  `unittest.mock.patch.object`) — and restore it after the test.
- Unit tests make no real network or database calls; reach those only through the project's existing
  integration-test setup (its fixtures, containers, or test database).

## Structure

Follow the AAA (Arrange-Act-Assert) structure defined in
[common/testing.md](../common/testing.md).
