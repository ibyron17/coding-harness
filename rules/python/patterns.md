---
paths:
  - "**/*.py"
  - "**/*.pyi"
---
# Python Patterns

> This file extends [common/patterns.md](../common/patterns.md) with Python specific content.

## Pure Modules vs. I/O Modules

Separate modules that touch the filesystem, clock, or environment from modules that don't. Mark
a pure module in its docstring so the boundary is explicit and checkable:

```python
"""hub_model.py — 허브 스냅샷 계약(HubSnapshot·HubConfig)과 그 직렬화·렌더(순수).

이 모듈은 파일시스템·시각·환경변수에 닿지 않는다(★순수, tests/hub/test_hub_model.py 대상).
"""
```

(`hub_model.py`'s own module docstring; the boundary is enforced mechanically, not just
documented — `tests/run.sh: T25-10` fails the suite if a `★순수` module imports
`open`/`Path`/`os`)

## Cross-Module Contracts

Let separate modules communicate only through frozen dataclasses, never through ad-hoc dicts
(see [coding-style.md](coding-style.md) for the `@dataclass(frozen=True)` convention). A module
header should say which dataclass is the contract and with whom (`hub_model.py` header).

## Expected Failures

Give an expected failure its own exception class instead of letting a raw `OSError` propagate,
when there is no lower-tier fallback to absorb it:

```python
class HubCollectError(Exception):
    """collect 파이프라인에서 예상된 실패(배포 자산 누락 등)를 나타낸다."""
```

(`hub_collect.py: HubCollectError` — anchor on the exception class name, not a line range)

## Leaf Modules Break Cycles

If two modules would otherwise import each other, extract the shared piece into a module that
imports nothing else from the package (a leaf module):

```python
"""hub_server_state.py — ... 어떤 허브 모듈도 임포트하지 않는 **잎 모듈**이다."""
```

(`hub_server_state.py` module docstring — the "잎 모듈" claim itself, not necessarily the
docstring's first line)
