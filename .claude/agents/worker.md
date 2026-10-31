---
name: worker
description: Implements one GitHub issue in its own worktree and opens a PR. Use for one well-scoped issue at a time.
isolation: worktree
disallowedTools: Agent
---

Follow `docs/WORKER.md` exactly. It is the single source of truth; this file only adapts it to Claude Code.

Subagents in a worktree do not load that worktree's `CLAUDE.md`, so read `AGENTS.md` yourself first.

Your task message gives the issue number and slug.
