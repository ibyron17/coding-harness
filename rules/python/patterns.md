---
paths:
  - "**/*.py"
  - "**/*.pyi"
---
# Python Patterns

> This file extends [common/patterns.md](../common/patterns.md) with Python specific content.

## Expected Failures Get Their Own Exception

Give an expected failure its own exception class instead of letting a raw `OSError`, `KeyError`, or
driver error propagate. At an API boundary, translate it once (e.g. a FastAPI exception handler) into
the error format the API already uses — never send the internal message or traceback to the client.

## Validate at the Boundary

Parse request bodies, configuration, and external responses into typed models at the edge (pydantic
where the project uses it); inner layers take those models, not raw dicts.

## Never Block the Event Loop

Inside `async def`, never call blocking I/O — `requests`, `time.sleep`, a synchronous DB driver, large
file reads. Use the async client the project already has, or offload the call (`asyncio.to_thread`,
Starlette's `run_in_threadpool`). In FastAPI a plain `def` endpoint already runs in a thread pool; an
`async def` endpoint does not.

## Dependencies Through the Framework

Get DB sessions, clients, and settings through the framework's injection mechanism (FastAPI `Depends`,
etc.) rather than module-level globals, so tests can override them.

## Leaf Modules Break Import Cycles

If two modules would otherwise import each other, move the shared piece into a module that imports
neither of them.
