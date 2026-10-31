# Hackathon template

A stack-agnostic starting repo for a team that works in parallel with coding agents.

## Using this template each hackathon
Clone the private template, change its remote to your new public hackathon repo, then push:
```sh
git remote set-url origin <new-url>
git push -u origin main
```
Open the repo in your agent and say: "Run KICKOFF.md".

## What is in it
- `AGENTS.md`: rules for coding agents (`CLAUDE.md` points to it).
- `scripts/`: the same five commands on every stack: `install`, `dev`, `lint`, `build`, `smoke`. Plus `worktree` (one git worktree per issue), `status` (what is set up and what is missing) and `check-scope` / `check-structure` / `check-secrets` (the CI gates).
- `docs/PARALLEL.md`, `INTAKE.md`, `ORCHESTRATOR.md`, `WORKER.md`, `REVIEWER.md`: how to work in parallel with several agents, from plain-English request to reviewed PR. Tool-neutral.
- `docs/START-HERE.md`: plain-English guide and teammate prompts. `docs/DEMO.md`: code freeze, known-good tag, rollback, submission checklist. `docs/STRUCTURE.md`: where files go.
- `.github/`: task issue template, PR template, and one required CI check.
- `docs/PROJECT.md`: what we are building and the demo script.
- `docs/PROJECT.md` sets `process: light` for exactly one person and `full` otherwise. `gates: warn` is the default; `strict` is only for events of 3+ days with 3+ coders. In warn mode scope, claim and structure concerns warn and work continues; strict mode blocks them.
- Out-of-scope ideas become GitHub issues labelled `idea`. Hackathon repos are public during the event; this template stays private.
- Secrets: [dotenvx](https://github.com/dotenvx/dotenvx) encrypts `.env`; `.env.keys` is never committed.

## Any agent, any model
- `AGENTS.md` is the single source of rules. Codex CLI and other tools that read `AGENTS.md` pick it up directly. Claude Code reads `CLAUDE.md`, which only imports `AGENTS.md`.
- If a tool wants its own filename, add a one-line stub that points to `AGENTS.md`. Check that tool's docs for the filename; I have not verified each one.
- Everything else (worktrees, orchestrator, workers) runs on git, `gh` and shell scripts. `.claude/agents/` holds optional Claude Code adapters; other tools can ignore it.

## Requirements
- Git, the GitHub CLI (`gh`), and a POSIX shell for `scripts/` (macOS and Linux have one; on Windows use Git Bash or WSL).
- dotenvx: `curl -sfS https://dotenvx.sh | sh`
