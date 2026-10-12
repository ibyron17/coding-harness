# Agent Orchestration

## Available Agents

Located in `~/.claude/agents/`. This repo ships **4 agents**; if the upstream ECC bundle (67 agents) is installed too, more may exist there.

| Agent | Purpose | When to Use |
|-------|---------|-------------|
| design-architect | Feature design, produces a design doc | Before implementation |
| implementer | Implementation | After design approval |
| code-reviewer | Code review | After writing code |
| Explore | Codebase search/summarization | Wide-scope lookups |

## Immediate Agent Usage

No user prompt needed:
1. New feature/structural change - Use **design-architect** agent
2. Design approved, ready to build - Use **implementer** agent
3. Code just written/modified - Use **code-reviewer** agent
4. Wide-scope lookup before a decision - Use **Explore** agent

## Parallel Task Execution

ALWAYS use parallel Task execution for independent operations:

```markdown
# GOOD: Parallel execution
Launch 3 agents in parallel:
1. Agent 1: Security analysis of auth module
2. Agent 2: Performance review of cache system
3. Agent 3: Type checking of utilities

# BAD: Sequential when unnecessary
First agent 1, then agent 2, then agent 3
```

## Delegation Completion Contract

Applies to every agent at every depth (parent, child, grandchild):

1. **Your final message IS the deliverable.** Never end your turn with "waiting for background agents" — a spawned task is not a completed task. Ending your turn while children are running orphans their results (completed children cannot notify a parent whose turn has ended).
2. **If you delegate, you own collection.** Wait for results, integrate them, then return. Fire-and-forget delegation is forbidden.
3. **Decompose only when the work cannot fit in one context.** Do not re-delegate a task already sized for a single agent — depth is an outcome, not a plan.

> Rationale: observed failure mode — research agents followed "Parallel Task Execution" above, spawned children, and returned "waiting" as their final answer. All children completed successfully but their results were orphaned. The parallel rule without a completion contract produces zombie tasks.

## Multi-Perspective Analysis

For complex problems, use split role sub-agents:
- Factual reviewer
- Senior engineer
- Security expert
- Consistency reviewer
- Redundancy checker
