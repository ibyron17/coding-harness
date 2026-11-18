---
paths:
  - "**/*.py"
  - "**/*.pyi"
---
# Python Security

> This file extends [common/security.md](../common/security.md) with Python specific content.

## Subprocess: argv List, Never a Shell

Pass a list of arguments to `subprocess.run`/`subprocess.Popen` and keep `shell=False`. Never build a
command string out of input (shell injection, and portability loss).

## SQL: Bind Parameters

Use the driver's or ORM's parameter binding — `cursor.execute(sql, params)`, SQLAlchemy
`text("... WHERE id = :id")` with bound values. Never format input into SQL with f-strings, `%`, or
`.format()`. An identifier that must vary (a sort column) comes from a fixed whitelist.

## No Path Assembly From Request Strings

Never build a filesystem path directly from request data. Either map a constrained token (a
fixed-length key) to a whitelisted path, or resolve the joined path and confirm it stays under the
base directory (`resolved.is_relative_to(base)`, 3.9+).

## Untrusted Data: Safe Loaders Only

`yaml.safe_load`, never `yaml.load`, `pickle`, or `eval` on data from outside the process.

## Secrets and Logs

- Read secrets from the environment or the project's settings object inside the function that needs
  them; don't keep them in module-level variables.
- Never log credentials. If a tool logs user prompts or other free text, mask token-shaped values
  before writing, and disclose the size cap, retention, and opt-out where the tool is installed.
