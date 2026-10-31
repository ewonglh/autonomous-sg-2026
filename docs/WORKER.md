# Worker

> A quick fix may skip an issue; see `docs/INTAKE.md`.

For issue-based work, take one GitHub issue and deliver one pull request. Quick fixes may skip the issue; see `docs/INTAKE.md`. You do not start other agents.

## Steps

1. **Read first:** `AGENTS.md`, `docs/PROJECT.md`, then the issue (`gh issue view <N>`) if there is one.
2. **Check where you are.** If you are already in `.worktrees/issue-<N>-<slug>` on branch `issue-<N>-<slug>`, start there and skip creation. Otherwise, when starting by hand, use `sh scripts/worktree new <N> <slug>`; it claims the issue. An orchestrator creates the worktree with `--no-claim` and assigns and labels the worker before starting them inside it. In `gates: strict`, use the issue worktree; in `gates: warn`, note any mismatch on the issue and continue. A harness may start from a stale copy of the default branch, so fetch origin and rebase if needed.
3. **Set up:** `sh scripts/install`. Use `sh scripts/dev` to run the app (it picks port 3000 + N from the worktree name).
4. **Plan briefly:** post two or three lines on the issue as a comment, if there is one.
5. **Implement** within the agreed scope and the issue's "Owner / files", if there is one, in small commits.
6. **Check:** run `sh scripts/lint`, `sh scripts/build` and `sh scripts/smoke`. These checks and `sh scripts/install` are hard gates; fix failures before proceeding. Never expose secrets. Scope, claim and structure problems are warnings in `gates: warn`: note them on the issue and continue. In `gates: strict`, they block. Do not edit a script or CI to make a check pass.
7. **Deliver:** push the branch (`git push -u origin HEAD`) and open a PR with `gh pr create`, filling in the PR template. Include `Closes #<N>` if there is an issue, plus the agent and model you used. For a quick fix, state the reason for skipping the issue in the PR.
8. **Comment** on the issue with the PR link, if there is one.

## Stop and report instead of continuing if
- a secret would be exposed, or install, lint, build or smoke fails. Fix the failure before continuing.
- otherwise, note scope, claim, structure or unclear-request concerns on the issue and continue with the smallest reversible change.

## Report (5 lines or fewer)
```
PR: <url>
Files changed: <list>
lint: pass|fail   smoke: pass|fail
Blocked or skipped: <none | what and why>
Noticed outside scope: <none | one line>
```

If you abandon the work, release your claim with `gh issue edit N --remove-label in-progress --remove-assignee @me --add-label ready`.

## Rules
- Do not read or edit other worktrees. In `gates: warn`, note a main-checkout or worktree mismatch and continue; in `gates: strict`, use your issue worktree.
- Never print, log or paste secrets, decrypted values or `.env.keys`.
- Do not merge, force-push, or touch `main`.
