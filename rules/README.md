# Rules
## Structure

Rules are organized into a **common** layer plus **stack-specific** directories.
This distribution is curated for a JavaScript/TypeScript + React + web stack, plus a recovered
Python ruleset (see below):

```
rules/
├── common/          # Language-agnostic principles (always loaded)
│   ├── coding-style.md
│   ├── git-workflow.md
│   ├── testing.md
│   ├── performance.md
│   ├── patterns.md
│   ├── hooks.md
│   ├── agents.md
│   ├── security.md
│   ├── code-review.md
│   ├── development-workflow.md
│   └── karpathy-guidelines.md
├── workflow/        # General dev workflow migrated from CLAUDE.md (always loaded)
│   ├── role-separation.md
│   ├── model-routing.md
│   ├── code-quality-baseline.md
│   └── project-instructions-checklist.md
├── python/          # Python specific (conditional)
├── react/           # React specific (conditional)
├── react-native/    # React Native / Expo specific (conditional)
├── typescript/      # TypeScript/JavaScript specific (conditional)
└── web/             # Web frontend specific (conditional)
```

- **common/** (11 files) contains universal principles — no language-specific code examples. **Always loaded at launch**, same priority as `CLAUDE.md`.
- **workflow/** (4 files) contains the general development workflow (role separation, model routing, code quality baseline, project-instructions checklist) migrated out of this repo's own `CLAUDE.md` so it deploys as user-scope rules instead of overwriting a project's `CLAUDE.md`. **Always loaded at launch**, same as `common/`.
- **typescript/**, **react/**, **react-native/**, **web/**, **python/** extend common rules with stack-specific patterns, tools, and code examples. Each file references its common counterpart.
- **Conditional loading via `paths` frontmatter**: Stack-specific files declare glob patterns in frontmatter (e.g., `paths: ["**/*.tsx"]`). A rule loads when Claude **reads or edits** a file matching the glob (not merely when matching files exist). Multiple globs are OR'd. See [Claude docs: Memory](https://code.claude.com/docs/en/memory).

## Installation

### Install All Rules (Default)

All 46 rules are installed. Rule files without `paths` frontmatter (common/, workflow/, README.md) are always loaded. Stack-specific files load only when their glob patterns match files in your project.

```bash
# Install to project directory (.claude/rules/)
./install.sh --scope project

# Or install to user home (~/.claude/rules/)
./install.sh --scope user
```

### How Conditional Loading Works

1. **Always loaded** (16 files):
   - `common/` (11 files: coding-style.md, git-workflow.md, karpathy-guidelines.md, etc.)
   - `workflow/` (4 files: role-separation.md, model-routing.md, code-quality-baseline.md, project-instructions-checklist.md — the general workflow this repo's `CLAUDE.md` used to carry)
   - This README
   - Loaded at launch alongside `CLAUDE.md`

2. **Conditionally loaded** (30 files):
   - `typescript/` (5 files) — loads when `**/*.ts`, `**/*.tsx`, `**/*.js`, `**/*.jsx` match
   - `react/` (5 files) — loads when `**/*.tsx`, `**/*.jsx`, or `components/`·`hooks/` sources match
   - `react-native/` (8 files) — loads when React Native/Expo sources match
   - `web/` (7 files) — loads when frontend files match (`**/*.tsx`, `**/*.css`, `**/*.html`, etc.)
   - `python/` (5 files) — loads when `**/*.py`, `**/*.pyi` match
   - Loaded only when glob matches project files
   - No setup required — matching happens automatically

## Rules vs Skills

- **Rules** define standards, conventions, and checklists that apply broadly (e.g., "80% test coverage", "no hardcoded secrets").
- **Skills** (`skills/` directory) provide deep, actionable reference material for specific tasks (e.g., `python-patterns`, `golang-testing`).

Language-specific rule files reference relevant skills where appropriate. Rules tell you *what* to do; skills tell you *how* to do it.

## Adding a New Language

To add support for a new language (e.g., `rust/`):

1. Create a `rules/rust/` directory
2. Add files that extend the common rules:
   - `coding-style.md` — formatting tools, idioms, error handling patterns
   - `testing.md` — test framework, coverage tools, test organization
   - `patterns.md` — language-specific design patterns
   - `hooks.md` — PostToolUse hooks for formatters, linters, type checkers
   - `security.md` — secret management, security scanning tools
3. Each file should start with:
   ```
   > This file extends [common/xxx.md](../common/xxx.md) with <Language> specific content.
   ```
4. Reference existing skills if available, or create new ones under `skills/`.

For non-language domains like `web/`, follow the same layered pattern when there is enough reusable domain-specific guidance to justify a standalone ruleset.

## Rule Priority

When language-specific rules and common rules conflict, **language-specific rules take precedence** (specific overrides general). This follows the standard layered configuration pattern (similar to CSS specificity or `.gitignore` precedence).

- `rules/common/` defines universal defaults applicable to all projects.
- `rules/typescript/`, `rules/react/`, `rules/web/` override those defaults where stack idioms differ.

### Example

`common/coding-style.md` recommends immutability as a default principle. A language-specific rules file (e.g., a `golang/coding-style.md`, if that language set is added) can override this:

> Idiomatic Go uses pointer receivers for struct mutation — see [common/coding-style.md](../common/coding-style.md) for the general principle, but Go-idiomatic mutation is preferred here.

### Common rules with override notes

Rules in `rules/common/` that may be overridden by language-specific files are marked with:

> **Language note**: This rule may be overridden by language-specific rules for languages where this pattern is not idiomatic.
