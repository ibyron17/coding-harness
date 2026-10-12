---
paths:
  - "**/*.py"
  - "**/*.pyi"
---
# Python Security

> This file extends [common/security.md](../common/security.md) with Python specific content.

## Don't Log Prompts or Credentials in Plaintext

If a tool logs prompt text or other user input, disclose the cap, retention period, and an
opt-out in its install-time notice (see `commands/hub.md`'s hook-install disclosure for a
worked example), and mask known secret token shapes before writing the log line — see
`hub_redact.redact_secret_tokens` for the reference implementation.

## Subprocess: argv List, Never a Shell

Pass a list of arguments to `subprocess.run`/`subprocess.Popen`. Never build a shell command string
(shell injection risk, and portability loss):

```python
subprocess.run(
    ["security", "find-generic-password", "-s", KEYCHAIN_SERVICE_NAME, "-w"],
    capture_output=True, text=True, timeout=KEYCHAIN_TIMEOUT_SECONDS, check=False,
)
```

(`hub_usage_fetch.py`, the `subprocess.run` call shown above — anchor on the call site,
not a line range)

## No Path Assembly From Request Strings

When serving files, never build a filesystem path out of a request string. Extract only a
constrained token (e.g. a fixed-length hex key) and use it solely as a lookup key into a
whitelist dictionary — the request string itself never reaches the filesystem:

```python
ALLOWED_REQUEST_PATHS = ("/", "/hub.html")
PROJECT_DASHBOARD_PATH_PATTERN = re.compile(r"^/project/([0-9a-f]{16})/dashboard\.html\Z")
```

(`hub_server.py`, the `ALLOWED_REQUEST_PATHS`/`PROJECT_DASHBOARD_PATH_PATTERN` constants
shown above — anchor on the constant names, not line numbers)

## Keep Tokens in Local Variables

Don't assign a credential or token to a module-level variable — keep it scoped to the function
that needs it, so it can't be read back by unrelated code later in the process lifetime.
