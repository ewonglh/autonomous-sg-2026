# Intake

Use this for work that needs an issue; quick fixes may go straight to a PR.

You turn a teammate's plain-English request into a small, approved GitHub issue. Any agent or model can do this. Needs `gh` and a logged-in account.

The person you talk to may not know how to code or use git. Use plain English, no jargon, and ask one question at a time (five at most).

## When to use it
- A teammate asks for a feature, change or fix and no issue exists for it.
- `sh scripts/status` reports "no open issues labelled ready".
- The orchestrator needs more issues.

## Steps

**Quick fix:** A change under about 30 lines, or any fix for a demo-breaking problem, may go straight to a PR without an issue. State the reason in the PR; an issue can be opened afterwards.

1. **Check the fit.** Check duplicates (`gh issue list --state all`, `gh pr list --state all`, and code search), overlapping `Owner / files` on open issues, and the cut list in `docs/PROJECT.md`. In `gates: warn`, give any concern as one-line advice; these checks do not block work.
2. **Understand the request.** Ask what the person wants to see or do when it works, who it is for, and anything they definitely do not want. The interview is with whoever is leading; do not require several people. Do not ask about technical choices; decide those from `docs/PROJECT.md` and `docs/STRUCTURE.md`.
3. **Make it small.** One outcome per issue, about one pull request (roughly 100 lines). Split big requests into several issues and say they depend on each other ("blocked by #N").
4. **Draft the issue** in the Task template format (`.github/ISSUE_TEMPLATE/task.md`):
   - **Goal:** one sentence.
   - **Owner / files:** the folders or files it touches, found from `docs/STRUCTURE.md` and the code. Include tests for those files; scope concerns are advice, not a blocker.
   - **Out of scope:** what this issue will not do.
   - **Acceptance:** plain, checkable sentences: "When I click X, I see Y."
   - **Env vars needed:** names only.
5. **Confirm the task:** show a short checklist, not the issue text: "I will build: ... I will not build: ... Does that match?" When the person already gave full detail, one confirmation is enough. Wait for a clear yes before creating a `task` issue.
6. **Create it:** create `task` issues after approval with `gh issue create --title "<title>" --body-file <file> --label task`. `idea` issues are not work and may be filed without approval. Read the issue number from the command output; do not guess it. The Plan owner is whoever led the interview. In `gates: warn`, the agent may add `ready` after the person's yes. In `gates: strict`, the Plan owner or Deputy adds `ready`.
7. **Say what happens next:** a person starting by hand uses `sh scripts/worktree new <N> <slug>`; an orchestrator creates the worktree with `--no-claim`, assigns and labels the worker, then the worker starts inside it. In `gates: warn`, work may start after the person's yes; in `gates: strict`, start once the issue has the `ready` label. Follow `docs/WORKER.md`.


## Rules
- Never create issues the person has not approved.
- Never put secrets, keys or personal data in an issue.
- If the request grows while work is under way, keep the current change small and mention the extra request as advice; it may become a separate approved issue. Out-of-scope ideas become issues labelled `idea`, not `task` or `ready`.
- Never decide the product for the person. Offer a default and let them choose.
