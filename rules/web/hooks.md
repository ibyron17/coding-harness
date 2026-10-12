---
paths:
  - "**/*.css"
  - "**/*.scss"
  - "**/*.sass"
  - "**/*.less"
  - "**/*.html"
  - "**/*.tsx"
  - "**/*.jsx"
  - "**/*.vue"
  - "**/*.svelte"
---
> This file extends [common/hooks.md](../common/hooks.md) with web-specific hook recommendations.

# Web Hooks

> Every hook JSON block below follows the official 3-tier schema — event name → matcher group →
> a `hooks` array of `{"type": "command", "command": ...}` entries. The canonical in-repo reference
> for this shape is `hub/bin/hub_settings.py`'s `_hub_hook_entry()`; a `type: "http"` entry does not
> fire (measured — see `docs/prps/hub-dashboard.md`).

## Recommended PostToolUse Hooks

Prefer project-local tooling. Do not wire hooks to remote one-off package execution.

### Format on Save

Use the project's existing formatter entrypoint after edits. Hooks do not receive the edited path as
a shell variable — it arrives via the `tool_input.file_path` field of the stdin JSON payload, so the
command reads stdin instead of interpolating one:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "node -e \"let d='';process.stdin.on('data',c=>d+=c);process.stdin.on('end',()=>{const p=JSON.parse(d).tool_input?.file_path;if(p)require('child_process').spawnSync('pnpm',['prettier','--write',p],{stdio:'inherit'})})\""
          }
        ]
      }
    ]
  }
}
```

Equivalent local commands via `yarn prettier` or `npm exec prettier --` are fine when they use repo-owned dependencies.

### Lint Check

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "node -e \"let d='';process.stdin.on('data',c=>d+=c);process.stdin.on('end',()=>{const p=JSON.parse(d).tool_input?.file_path;if(p)require('child_process').spawnSync('pnpm',['eslint','--fix',p],{stdio:'inherit'})})\""
          }
        ]
      }
    ]
  }
}
```

### Type Check

Use `--incremental` so re-runs reuse the previous `.tsbuildinfo` (1-3s on unchanged code instead of 30-60s every time). Wrap in `timeout` so a stuck tsc gets reaped by the OS instead of accumulating across edits — this prevents the multi-process buildup that happens when edits fire faster than tsc finishes.

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "timeout 60 pnpm tsc --noEmit --pretty false --incremental --tsBuildInfoFile node_modules/.cache/tsc-hook.tsbuildinfo"
          }
        ]
      }
    ]
  }
}
```

**Why both flags matter:**
- Without `--incremental`, every edit re-checks the entire program from scratch. On a real Next.js project this stacks fast: edits at 5-10s intervals + 30-60s tsc runs = N concurrent tsc processes.
- Without `timeout`, a tsc that hangs (transitive dep change, type-checker stuck on a recursive type) never exits and orphans when the parent shell does.
- `--tsBuildInfoFile` is required because `--noEmit` normally suppresses the buildinfo write; specifying the path explicitly keeps incremental working.

If you're on Windows without GNU coreutils, swap `timeout 60` for a PowerShell wrapper or rely on a Stop/SessionEnd hook to sweep stale tsc processes.

### CSS Lint

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "node -e \"let d='';process.stdin.on('data',c=>d+=c);process.stdin.on('end',()=>{const p=JSON.parse(d).tool_input?.file_path;if(p)require('child_process').spawnSync('pnpm',['stylelint','--fix',p],{stdio:'inherit'})})\""
          }
        ]
      }
    ]
  }
}
```

## PreToolUse Hooks

### Guard File Size

Block oversized writes from tool input content, not from a file that may not exist yet:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Write",
        "hooks": [
          {
            "type": "command",
            "command": "node -e \"let d='';process.stdin.on('data',c=>d+=c);process.stdin.on('end',()=>{const i=JSON.parse(d);const c=i.tool_input?.content||'';const lines=c.split('\\n').length;if(lines>800){console.error('[Hook] BLOCKED: File exceeds 800 lines ('+lines+' lines)');console.error('[Hook] Split into smaller modules');process.exit(2)}console.log(d)})\""
          }
        ]
      }
    ]
  }
}
```

## Stop Hooks

### Final Build Verification

```json
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "pnpm build"
          }
        ]
      }
    ]
  }
}
```

## Ordering

Recommended order:
1. format
2. lint
3. type check
4. build verification
