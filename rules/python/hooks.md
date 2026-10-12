---
paths:
  - "**/*.py"
  - "**/*.pyi"
---
# Python Hooks

> This file extends [common/hooks.md](../common/hooks.md) with Python specific content.

## Hook and Statusline Entry Points Always Exit 0

An entry point invoked by the Claude Code hook system must never block the session. Catch every
exception at the top level of `main()` and return 0 regardless:

```python
def main() -> int:
    """항상 0 을 반환한다 — 이 훅이 세션 진행을 막는 일은 원리적으로 없어야 한다."""
    try:
        _run()
    except Exception:
        pass
    return 0
```

(`hub_hook.py: main()` — anchor on the function name, not a line number; the same shape in
`hub_statusline.py: main()`)

This top-level `except Exception` swallow is allowed **only** at this one entry-point boundary —
not inside helper functions, where a real error should still propagate.

## Keep the Entry Point Itself Fast

The entry point's own work should be milliseconds (append + light bookkeeping). Spawn a detached
subprocess for anything heavier instead of doing it inline (`hub_hook.py` module docstring).
