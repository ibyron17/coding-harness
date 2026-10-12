---
paths:
  - "**/*.py"
  - "**/*.pyi"
---
# Python Coding Style

> This file extends [common/coding-style.md](../common/coding-style.md) with Python specific content.

## Standard Library First

Prefer the standard library over third-party packages. Add a dependency only as an explicit,
documented decision — this repo's own Python (`hub/bin/*.py`) has zero third-party imports.

## Type Hints

Add type hints to every function signature, including the modern `X | None` union syntax (3.10+):

```python
def read_server_heartbeat_mtime_ms() -> int | None:
    ...
```

(`hub_collect.py`, `read_server_heartbeat_mtime_ms()` — anchor on the function name, not a
line number; the same convention recurs elsewhere in `hub/bin/*.py`)

## Immutability

Use `@dataclass(frozen=True)` to make data structures immutable by construction:

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class HubConfig:
    server_port: int = 8794
```

(`hub_model.py`'s `HubConfig`/`HubSnapshot` — anchor on the class name, not a line number;
the same `@dataclass(frozen=True)` convention recurs across other `hub/bin/*.py` modules,
non-exhaustively — e.g. `hub_parse.py`, `hub_session.py`, `hub_usage.py`)

## Constants

Declare module-level constants in `UPPER_SNAKE_CASE`. Explain *why* the value was chosen, not just
what it is — a bare number invites someone to change it without knowing what breaks:

```python
# 400자(호스트 실측 최대) + 말줄임표 1자(구현 2회차 검수 C-1). label 을 비롯해 이슈 3(WT3)
# 으로 제거된 세 발췌성 필드도 한때 hub.html 에 인라인되는 발췌성 콘텐츠로 같은 상한을
# 공유했다. ...
WORKFLOW_PREVIEW_MAX_CHARS = 401
```

(`hub_workflow.py`, `WORKFLOW_PREVIEW_MAX_CHARS` — anchor on the constant name, not a line range)

## Private Helpers

Prefix module-private helper functions with a leading underscore:

```python
def _clip_to_length(value: str, max_chars: int) -> str:
    ...
```

(`hub_workflow.py: _clip_to_length()` — anchor on the function name, not a line number; the
same helper shape recurs in `hub_transcript.py`·`hub_subagent.py`, each kept as its own
3-line copy rather than a shared import — see `hub_subagent.py`'s module docstring for why)

## Paths

Use `pathlib.Path` for filesystem paths, not string concatenation.
