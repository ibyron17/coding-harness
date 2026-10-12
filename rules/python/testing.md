---
paths:
  - "**/*.py"
  - "**/*.pyi"
---
# Python Testing

> This file extends [common/testing.md](../common/testing.md) with Python specific content.

## Framework

Use stdlib **`unittest`** as the default framework — not pytest. This repo's own Python tests run
on it exclusively — every `test_*.py` module under `tests/hub/` — in line with
the "Standard Library First" rule in [python/coding-style.md](coding-style.md). Adopt pytest only
as an explicit decision recorded in the project's own `CLAUDE.md` (see the "Rule Priority" section
of [rules/README.md](../README.md), which defines the Language note convention).

```bash
python3 -m unittest discover -s <dir> -t <root>
```

(`tests/run.sh: test_hub_unit_tests()` / T24 — anchor on the function name, not a line
number)

## Test Isolation

Isolate tests that touch module-level state by swapping the module constants in `setUp` and
restoring them in `tearDown`, rather than mocking the module itself:

```python
def setUp(self) -> None:
    self.original_events_dir = hub_collect.EVENTS_DIR
    hub_collect.EVENTS_DIR = self.temp_dir / "events"

def tearDown(self) -> None:
    hub_collect.EVENTS_DIR = self.original_events_dir
```

(`test_hub_hook.py`, `HubHookScenarioTest.setUp` / `tearDown`)

## Mocking

Use `unittest.mock.patch.object` to replace a specific module function, and `mock.patch` for
dotted paths (`subprocess.Popen`, `sys.stdin`):

```python
with mock.patch.object(hub_collect, "collect_snapshot") as mock_collect_snapshot:
    ...
```

(`test_hub_hook.py`, `SpawnsBackgroundCollectTest`)

## Structure

Follow the AAA (Arrange-Act-Assert) structure defined in
[common/testing.md](../common/testing.md).
