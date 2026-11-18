---
paths:
  - "**/*.py"
  - "**/*.pyi"
---
# Python Coding Style

> This file extends [common/coding-style.md](../common/coding-style.md) with Python specific content.

## The Project's Toolchain Comes First

Read what the project already pins before writing code, and follow it over any default here:

- **Python version** — `requires-python` in `pyproject.toml` (or `.python-version`) bounds the syntax
  you may use: `X | None` and `match` need 3.10+, `typing.Self` 3.11+. Below 3.10, write `Optional[X]`.
- **Formatter, linter, type checker** — whatever `pyproject.toml` configures (`[tool.ruff]`,
  `[tool.black]`, `[tool.isort]`, `[tool.mypy]`, …). Run those; don't add a second tool or reformat
  code you didn't change.
- **Libraries** — use what the project already depends on (its model library, HTTP client, settings
  loader) instead of re-implementing it with the standard library. A *new* dependency is still an
  explicit, justified proposal — the standard library or an existing dependency first.

## Type Hints

Annotate every public function signature, in the style the codebase already uses.

## Immutability

Make value objects immutable by construction with the model type the project already uses —
`@dataclass(frozen=True)`, a frozen pydantic model, or `NamedTuple`.

## Constants and Private Helpers

- Module-level constants in `UPPER_SNAKE_CASE`. When the value isn't self-evident, say *why* it was
  chosen — a bare number invites someone to change it without knowing what breaks.
- Prefix module-private helper functions with a leading underscore.

## Paths

Use `pathlib.Path` for filesystem paths, not string concatenation.
