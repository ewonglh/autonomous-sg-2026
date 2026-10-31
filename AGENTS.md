# CrowdPulse – agent rules

Read this before changing anything. Keep it short; add to "Known gotchas" when something bites.
What we are building, who it is for, and the demo script: `docs/PROJECT.md`.

## First run

At the start of every session, run `sh scripts/status`. It lists what is missing, in priority order, and ends with a "Next:" line.

- If it shows BLOCKED lines (project not described, scripts or CI not set up), tell the user and do that first. For an unconfigured project, follow `KICKOFF.md`. Do not start feature work until nothing is BLOCKED.
- If it shows TODO lines (missing labels, no ready issues), mention them and handle them when the user's request allows. For issues, follow `docs/INTAKE.md`.
- If the user's request is only a question, answer it. No setup needed.

## Commands

The commands are the same on every stack. Only the contents of `scripts/` change.

- install: `sh scripts/install`
- run: `sh scripts/dev` (injects secrets with dotenvx; set `PORT` per worktree)
- lint and typecheck: `sh scripts/lint`
- build: `sh scripts/build`
- smoke test: `sh scripts/smoke`
- scope, structure and secrets checks: `sh scripts/check-scope`, `sh scripts/check-structure`, `sh scripts/check-secrets`
- project setup state: `sh scripts/status` (read-only; run it at the start of every session)

If `sh` is not found (for example in Windows PowerShell), use Git Bash (`C:\Program Files\Git\bin\sh.exe`) or WSL; do not skip the scripts.

Never call the stack's own commands directly in docs, issues or CI. Use the scripts, and edit a script if the stack changes.

## Priorities

- A working demo beats clean architecture. Make the smallest change that works.
- Do not add dependencies without asking the team.
- Do not refactor code outside your issue.

## Engineering rules

- Do only what the issue asks. Out-of-scope ideas become GitHub issues labelled `idea`.
- One purpose per file and per function. Keep files under the `max-lines` limit in `.structure`.
- Do not copy logic a third time: extract it. Do not add an abstraction, library or setting until two places need it.
- Do not reach through objects (`a.b.c.d`). Ask the object that owns the data.
- Put files where `docs/STRUCTURE.md` says. Ask before adding a top-level folder; it needs an `allow` line in `.structure`.
- Explain what you did in plain English; the person you work with may not know how to code.

## Process mode

`docs/PROJECT.md` sets `process: light` only for exactly one person; otherwise `full`. It also sets `gates: warn` (default) or `strict`; use strict only for events of 3+ days with 3+ coders. In warn mode scope, claim and structure concerns warn and work continues; strict mode blocks those concerns. Merger and Deputy matter only in strict mode.

## Workflow

- In full mode, use an issue except for a change under about 30 lines or a demo-breaking fix. Ideas become GitHub issues labelled `idea`. For other new work, follow `docs/INTAKE.md`: draft the issue, show a plain-English checklist, create it only after approval, then build.
- If the request grows while you work, stop and raise a new issue. Do not widen the current one.
- Full mode: one issue, one branch (`issue-<N>-<slug>`), one worktree, one PR that says `Closes #N`.
- Start: `sh scripts/worktree new <N> <slug>` (claims the issue by assigning it and setting `in-progress`; in warn mode concerns warn and work continues, while strict mode may refuse if it is already taken, fetches, fast-forwards your local default branch, creates `.worktrees/issue-<N>-<slug>` from the latest remote default branch, and copies `.env.keys`), `cd` into it, then `sh scripts/install`.
- Ports: `sh scripts/dev` picks `3000 + N` from the worktree name (issue N), so worktrees never collide.
- Record progress as comments on the issue, not in code comments or PR threads.
- Stay inside the files your issue owns. If you need another module, comment on the issue and ask first.
- Keep PRs small (about 100 lines). Rebase on `main` before opening. We squash-merge.
- Unfinished work that must merge goes behind a flag or stays out of the demo path.

## Parallel agents

These rules are tool-neutral: they use only git, `gh` and `scripts/`, so any agent or model can follow them.

- Roles are in `docs/ORCHESTRATOR.md` and `docs/WORKER.md`. Worktree and shared-dependency details are in `docs/PARALLEL.md`.
- Stay inside your own worktree folder. Do not read or edit other worktrees or the main checkout.
- Trust `sh scripts/lint` and `sh scripts/smoke`, not your own claim that it works.
- Do not start other agents unless you are the orchestrator.
- In full mode, every PR gets an independent review (`docs/REVIEWER.md`) before a human merges. The reviewer is advisory.

## Secrets

- The encrypted `.env` is committed. `.env.keys` is never committed. `sh scripts/dev` already wraps the app in `dotenvx run --`.
- Never print, log or paste decrypted values or `.env.keys` into chat, issues or PRs.
- Never read `.env.keys`, and never run a command that prints decrypted values (for example `dotenvx get` or `dotenvx run -- env`).
- If a secret or `.env.keys` appears in chat, an issue or a PR, tell the owner and treat it as compromised.
- Agents never receive secret values. A human sets or changes a secret in their own terminal (`dotenvx set KEY value`) and commits the updated encrypted `.env`. If a task needs a new variable, add its name to `.env` with an empty value and ask a human to fill it in.

## Boundaries

- Ask before any command that throws work away (`git reset --hard`, `git clean`, `git checkout -- <path>`, `git branch -D`, deleting folders). Never force-push.
- Never commit build artefacts. Ask before changing the database schema or touching CI.

## Definition of done

- The app runs locally with `sh scripts/dev`.
- `sh scripts/lint` and `sh scripts/smoke` pass.
- `sh scripts/check-scope`, `sh scripts/check-structure` and `sh scripts/check-secrets` pass.
- The demo path still works end to end.
- After the code freeze in `docs/PROJECT.md`, only demo-path fixes. Demo, tagging and rollback: `docs/DEMO.md`.
- README updated if setup changed.

## Known gotchas

- (Teams append here.)
