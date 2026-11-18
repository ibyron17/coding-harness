---
paths:
  - "**/*.py"
  - "**/*.pyi"
---
# Python Hooks

> This file extends [common/hooks.md](../common/hooks.md) with Python specific content.

## Run the Formatter and Linter the Project Configures

If you add an edit-time hook (PostToolUse) for Python files, have it run the tools the project
configures in `pyproject.toml` — e.g. `ruff format` + `ruff check --fix`, or black + isort — through
its environment manager (`uv run`, `poetry run`). Don't introduce a formatter the project doesn't use.
