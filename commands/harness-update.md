---
description: "Update coding-harness to latest version — fetch repo, pull changes, and reinstall"
disable-model-invocation: true
---

# Environment Update

> Maintains coding-harness in sync with repo changes. Reads install manifest, checks for updates, and reinstalls automatically. Confirmation is reserved for genuinely ambiguous or destructive situations (diverged branches, a file that looks like a deliberate local customization) — routine pull/reinstall/hub-restart steps proceed without asking.

**Automated Phases**: find → fetch → pull → reinstall → verify

---

## Phase 1 — FIND MANIFEST

**Goal**: Locate install manifest to discover repo path and scope.

1. Check for `.claude/.coding-harness.json` in `$PWD` (project scope)
2. If not found, check `~/.claude/.coding-harness.json` (user scope)
3. If neither exists → **Fallback**: Ask user for repo path interactively

### Manifest Validation

When found, verify:
- `version` ∈ { 1, 2, 3 } (v1 = pre-ledger manifest, v2 = adds the `files` sha256 ledger install.sh uses for stale/modified classification and tombstone deletion — see install.sh's `check_directory_conflict`/`process_removals`, v3 = drops CLAUDE.md from that ledger since install.sh no longer deploys it — see `retire_user_claude_md`)
- `repo_path` exists and is a directory
- `scope` ∈ { "project", "user" }

If validation fails, report the error and stop.

### Fallback: Interactive Input (No Manifest)

```
[INFO] Install manifest not found.
[INFO] Enter the coding-harness repo path (or 'skip' to abort):
> /path/to/coding-harness
```

If user enters a valid path → continue with Phase 2 (but don't create manifest).  
If user enters 'skip' or Ctrl+C → stop without error.

---

## Phase 2 — FETCH & DETECT

**Goal**: Check for upstream changes.

```bash
cd "$repo_path"
```

### Check repo status

```bash
git status
```

If not a git repository → **ERROR**: "Not a git repository: $repo_path"

Log status (dirty/detached state is OK, just warn):
- Dirty: `[WARN] Working tree has uncommitted changes. Continuing...`
- Detached HEAD: `[WARN] Repository is in detached HEAD state. Continuing...`

### Verify upstream

```bash
git rev-parse --abbrev-ref '@{u}'
```

If command fails (no tracking branch set) → **ERROR**: "Tracking branch not set. Run: git branch --set-upstream-to=origin/main" → stop.

### Fetch origin

```bash
git fetch origin
```

If fails → **ERROR**: "Failed to fetch from origin"

### Check installed manifest freshness

```bash
git -C "$repo_path" rev-parse HEAD
```

Compare this HEAD against the `installed_from_commit` field of the manifest read in Phase 1:

- No manifest was found (interactive fallback path), the `installed_from_commit` field is missing, or its value is `"unknown"` → treat the install as **stale**
- `installed_from_commit` != current HEAD → **stale**
- `installed_from_commit` == current HEAD → **fresh**

### Detect changes

```bash
git log --oneline 'HEAD..@{u}'   # commits in remote not in local
git log --oneline '@{u}..HEAD'   # commits in local not in remote (divergence)
```

If local has commits not in remote AND remote has commits not in local → **ERROR**: "Branches have diverged. Manual resolution required."

If no new commits in upstream AND the install is fresh → **INFO**: "Already up to date. No changes." → exit 0

If no new commits in upstream but the install is stale:

```
[INFO] Repo is up to date, but the installed files are from an older commit.
[INFO] Repo HEAD:      <repo HEAD, short hash>
[INFO] Installed from: <installed_from_commit, short hash (or "unknown")>
[INFO] Reinstalling...
```

Skip Phase 3 (there is nothing to pull) and continue directly to Phase 4. No confirmation — reinstalling from an already-fetched, non-diverged repo only touches managed files and is caught by Phase 4's own conflict check if anything unexpected is in the way.

If new commits exist:

```
[INFO] Remote has N new commits:
  <log output here>
[INFO] Updating...
```

Continue to Phase 3. No confirmation — `git pull --ff-only` cannot lose local work; it fails closed on any conflict (handled in Phase 3), never silently merges or rewrites history.

---

## Phase 3 — PULL

**Goal**: Fast-forward merge.

If Phase 2 triggered a reinstall because only the installed files were stale (no new upstream commits), skip this phase — there is nothing to pull — and go directly to Phase 4.

```bash
git pull --ff-only
```

If fails (merge conflict) → **ERROR**: "Pull failed with conflicts. Please resolve manually and run harness-update again."

Report: `[OK] Merged N commits`

---

## Phase 4 — REINSTALL

**Goal**: Run install.sh in the correct context.

If the installed copy predates the dashboard-into-hub migration, this reinstall's tombstone
processing (`removals.txt`) removes the old `commands/dashboard*` files from this target — that
functionality now lives with the hub (see Phase 4b) and no longer ships with coding-harness itself.

### For project scope

**IMPORTANT**: The install.sh --scope project must run from the target project directory.

```bash
cd "$target_base_dir"
"$repo_path/install.sh" --scope project
```

If exit 0 → continue to Phase 5.

If exit 1 (diff conflict reported by install.sh):

```
[WARN] Install reported conflicts in modified files.
```

install.sh classifies this automatically against the sha256 ledger recorded at the previous
install (the manifest's `files` field) — a differing file whose current hash still matches what was
recorded is a **stale copy** (this machine's install is simply behind the repo) and install.sh
passes it through without requiring `--force`; only a file whose hash no longer matches the ledger
(**modified**, meaning it changed after installation — a deliberate local customization or a
manual edit) reaches this conflict report. So what `exit 1` here means: **every** file still listed
is a suspected local modification. Don't interpret content to decide staleness vs. customization —
install.sh already made that determination before this exit code fired.

Show the file list install.sh already printed — one `diff -rq` summary line per file (`Files
<repo path> and <target path> differ`, capped at `MAX_DIFF_LINES` entries with a trailing count
of the rest), not the diff content itself — and ask **once** whether to overwrite the whole batch
with `--force` — this is the one place in this command that still asks, because every file
reaching this point is a suspected local modification, not routine drift. Mention before asking:
confirming `--force` isn't scoped to just the files shown above — install.sh's precondition
chain checks the three managed directories (rules/agents/commands) in sequence and stops at the
first conflicting one, so directories after that point aren't even evaluated until `--force` is
given. Once given, `--force` backs up every modified file it finds across all three directories,
each to a sibling `.bak-<timestamp>` copy of the pre-overwrite content — no automatic cleanup, so
flag it if backups could pile up. If confirmed:
```bash
cd "$target_base_dir"
"$repo_path/install.sh" --scope project --force
```

If exit 0 → continue to Phase 5.
If exit 1 again → **ERROR**: "Force reinstall failed. Resolve manually." → exit 1
If the user declines → stop without forcing; report which files were left conflicting.

### For user scope

```bash
"$repo_path/install.sh" --scope user
```

Same conflict handling as above. `--scope user` additionally retires any previously-installed
`~/.claude/CLAUDE.md` (older versions of this repo deployed it; this version no longer does) — it
renames the file to a timestamped `.retired-<timestamp>` copy when it can prove the file is
unmodified (a hash-ledger match, or for legacy pre-ledger installs, a matching title/body sentinel
pair), and otherwise leaves it in place with a protected note. This is silent and automatic and
needs no confirmation from this command — see `retire_user_claude_md` in install.sh.

---

## Phase 4b — HUB REINSTALL (conditional)

**Goal**: Keep the independently-installed hub (if present) in sync with the repo, without ever
starting a server the user didn't already have running. Hub is installed separately from
coding-harness (`hub/install.sh`), so this phase only acts when it detects an existing installation.

### Detect

```bash
test -f "$repo_path/hub/bin/hub.py" && test -f "$HOME/.claude/hub/bin/hub.py"
```

Actually check the **installed target** (`~/.claude/hub/bin/hub.py`), not the repo copy:

```bash
test -f "$HOME/.claude/hub/bin/hub.py"
```

If not found:
```
[INFO] Hub is not installed. Skipping.
```
Continue to Phase 5. **Do not create anything.**

### Skip if already up to date

Before touching a running server, check whether reinstalling would even change anything.
Stopping and restarting a server just to have it come back running the exact same code is pure
interference, not an update.

```bash
diff -rq -x __pycache__ "$repo_path/hub/bin" "$HOME/.claude/hub/bin"
diff -rq "$repo_path/hub/rules" "$HOME/.claude/rules/hub"
```

The first line is the same comparison `hub/install.sh` uses internally
(`list_differing_managed_files`) to decide whether a modified-file conflict exists. The second
line covers the rules channel (`hub/install.sh` also deploys `hub/rules/*.md` to
`~/.claude/rules/hub/`, docs/prps/dashboard-into-hub.md HD11) — `bin/` can be identical while a
rules file changed, and that alone should still trigger a reinstall.

Evaluate the two `diff` commands independently — call a command "clean" when its output is empty
or every line is an `Only in ...` line naming an **installed target** directory
(`$HOME/.claude/hub/bin` or `$HOME/.claude/rules/hub`), and "dirty" otherwise (any
`Files ... differ` line, any `Only in ...` line naming a **repo** directory, or a command error).

- **Both clean** — **skip everything below** (do not call server-status, server-stop,
  server-start, or `hub/install.sh`). Report:
  ```
  [INFO] Hub is already up to date. Skipping (server left as is).
  ```
  Then continue to Phase 5.
- **bin/ dirty** (rules/ clean or dirty, doesn't matter) — **proceed with steps 1-5 below**: the
  running server process needs the code swap, so it goes through the full stop → reinstall →
  restart dance.
- **bin/ clean, rules/ dirty** — a rules-only change never touches the running server process (the
  server doesn't read `hub/rules/*.md`), so stopping and restarting it here would be the same
  needless interference the "Skip if already up to date" check exists to prevent (docs/prps/
  dashboard-into-hub.md HD11, extending the `9f23534` fix — "don't touch the server when nothing
  it runs has changed"). Skip step 1 (server-status), step 2 (server-stop), and step 4
  (server-start) entirely. Run only step 3 (reinstall, including its `--force` retry on a
  modified-files conflict) and report:
  ```
  [INFO] Hub rules changed but bin/ did not — reinstalling without touching the server.
  ```
  Then continue to Phase 5.

Limitation: this only compares files on disk, not the running process. If `hub/install.sh` was
run by hand at any point after the current server process started (the server outlives
sessions), that server keeps executing the old code even though the files now match —
`/hub server restart` is the fix for that case.

### If found

1. Check server status:
   ```bash
   python3 -- "$HOME/.claude/hub/bin/hub.py" server-status --json
   ```
   Read the `alive` field.

2. If `alive == true`, stop it — no confirmation needed, this is the expected end-to-end update:
   ```
   [INFO] Hub server is running. Stopping, updating, and restarting...
   ```
   `python3 -- "$HOME/.claude/hub/bin/hub.py" server-stop --json`, remember that the server was
   running (`was_running_before_update=true`). Stopping and restarting the hub server is safe —
   it's a local process with no in-flight user data to lose, and step 4 restores it automatically.

   If `alive == false`, continue directly (nothing to stop).

3. Reinstall:
   ```bash
   "$repo_path/hub/install.sh"
   ```
   - exit 0 → continue to step 4.
   - exit 1 (modified-files conflict): `hub/install.sh` has no manifest at all, so it cannot
     classify a differing file as stale vs. modified on its own (unlike Phase 4's root
     `install.sh`, which has the sha256 ledger to do that automatically). Judge each flagged
     file yourself: **looks
     like plain staleness** (older/edited version of the same distributed content) → no
     confirmation needed; **looks like a deliberate local customization** (content clearly
     written for this machine, no upstream counterpart) → hold that file back and ask about it
     specifically. Don't let one held-back file block the rest — proceed with `--force` for
     everything else. Rerun `"$repo_path/hub/install.sh" --force` once the call is made.
     If that `--force` retry **also** exits 1 (e.g. a symlink-rejection error, which `--force`
     does not bypass by design), stop retrying — this isn't a modified-file conflict `--force`
     can resolve. If the server was running before this phase (`was_running_before_update=true`),
     restore it via step 4, then report the exit 1 and its error output as-is.

4. If the server was running before this phase started (`was_running_before_update=true`):
   ```bash
   python3 -- "$HOME/.claude/hub/bin/hub.py" server-start --json
   ```
   This restores the state the server was actually in before this phase touched it — it is not a
   fresh, unprompted start. A server that was off before `/harness-update` stays off.

5. Hooks are never touched here. If the hook command string ever changes, `install-hooks` is
   idempotent, so just note:
   ```
   [INFO] If needed, run /hub install again to refresh the installed hook command.
   ```

---

## Phase 5 — VERIFY MANIFEST

**Goal**: Confirm installation succeeded.

The install.sh script automatically updates the manifest's `installed_from_commit` when successful.

Verify:
```bash
cat "$manifest_path" | grep -q "installed_from_commit"
```

Extract current HEAD:
```bash
git -C "$repo_path" rev-parse HEAD
```

If `installed_from_commit` in manifest equals current HEAD → **OK**: Installation verified.

Report:
```
[OK] Update complete
[OK] Manifest updated: installed_from_commit = <hash>
```

If mismatch → **WARN**: "Manifest commit mismatch. Manifest may not have been updated."

Exit 0.

---

## Error Handling Summary

| Condition | Action |
|-----------|--------|
| Manifest not found | Fallback: ask user for repo path |
| Not a git repo | ERROR: stop |
| No tracking branch | ERROR: stop with `git branch --set-upstream-to` hint |
| Fetch fails | ERROR: stop |
| Branches diverged | ERROR: stop |
| Already up to date (repo and install both fresh) | INFO: stop, exit 0 |
| Repo up to date but install stale | INFO: reinstall automatically, skip Phase 3, proceed to Phase 4 |
| Pull fails | ERROR: stop |
| install.sh conflict | WARN: install.sh already classified every listed file as modified (ledger mismatch) — show the list (`diff -rq` summary lines, not full diff content; may be a subset — the precondition chain stops at the first conflicting directory) and ask once for a batch `--force`, noting it backs up every modified file across all three managed directories |
| install.sh force fails | ERROR: stop |
| Hub not installed | INFO: skip Phase 4b, no error |
| Hub already up to date (both bin/ and rules/ comparisons match) | INFO: skip reinstall and restart entirely, server left as is |
| Hub bin/ clean but rules/ dirty | INFO: reinstall only (`hub/install.sh`), never touch the server (it doesn't read hub/rules/*.md) |
| hub/install.sh conflict | WARN: hub/install.sh has no ledger — judge each file yourself (Phase 4b), auto `--force` for plain staleness, ask only about files that look like deliberate customization |
| Hub server running and hub bin/ differs | INFO: stop, reinstall, restart automatically — no confirmation |
| Manifest verification fails | WARN: report mismatch but exit 0 |

---

## Notes

- **Manifest is runtime metadata**: Not part of the deployed files, so it's never backed up or version-controlled.
- **User modifications**: If local rules/agents/commands are modified, install.sh requires `--force` to overwrite — and when it does, it first backs up each modified file to a sibling `.bak-<timestamp>` copy of the pre-overwrite content (no automatic cleanup). Root install.sh (Phase 4) decides stale-vs-modified itself from the manifest's sha256 ledger — a stale copy is reinstalled without asking (and without a backup, since nothing of the user's is at risk), and only genuinely modified files reach the confirmation prompt and get backed up. `hub/install.sh` (Phase 4b) has no such ledger, so that judgment is still made from the diff content.
- **Dirty repo is OK**: Minor uncommitted changes won't block the update. Major conflicts will be caught by install.sh.
- **Why the manifest freshness check exists**: Contributors who commit directly in this repo are always at or ahead of `@{u}`, so `git log HEAD..@{u}` is permanently empty for them. Without comparing `installed_from_commit` to repo HEAD, Phase 4's reinstall would never run for that workflow, and the installed files would silently drift out of date.
