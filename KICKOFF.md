# Kickoff

Run this once. Tell your agent: **"Run KICKOFF.md."** Keep it under 10 minutes of user time.

You are the kickoff agent. Interview the user, then fill in every TODO in this repo so the template becomes a running project.

## Rules for the kickoff agent
- Start with step 0. The person leading makes the product decision, with optional team input; the agent never chooses an idea for them.
- Interview whoever is leading. Ask at most the six questions in step 1 in one message, with a suggested default where you can. Ask a follow-up only if an answer blocks you.
- Never ask the user to paste secrets, API keys or passwords into chat. If a key is needed, create the variable name with an empty value and tell the user to set it themselves (step 5).
- Do not push, open PRs or create GitHub issues without asking first.
- There is no starter app in this repo: you create the scaffold yourself (initialise the chosen stack, write the smallest server or page). Keep it minimal: the smallest app that runs and shows the demo's first step. Do not stop because no scaffold exists.
- Check `gh pr list --head kickoff --state open --json number`. If a kickoff PR is already open, note it and continue with that PR instead of opening a duplicate.

## 0. Pick an idea, if needed
If the team already has an idea, use it and continue to step 1. If not, offer three candidate ideas that fit the event theme and judging rules. For each idea, give one plain sentence for each of these criteria:
- Can we demo it in the time left?
- Does it match the judging rules or theme?
- Is the data or API it needs available?

Ask the person leading, and any available teammates, to pick one or suggest their own. Wait for their decision; do not pick for them.

## 1. Interview
Ask these, and nothing else:
1. **What are we building, and for whom?** One or two sentences.
2. **Stack:** language and framework, database (if any), and where it deploys. If the user is unsure, ask what the team already knows, then recommend one stack and say why in one line.
3. **Team:** who is on it (GitHub handles), which module or area each person owns, and who is leading? The leader is the Plan owner. Merger and Deputy are optional by default and named only for strict gates; the Deputy may be `none`. One person may hold every role. The Deputy covers the Plan owner (including adding `ready`) and the Merger when they are away.
4. **Demo:** the three steps a judge will see. This becomes the smoke test.
5. **External services:** which APIs or services it needs (names only), and the deadline.
6. **Event:** how long you have (hours or days), how many people will work on it, and how many will code.

## 2. Fill in the project
- `docs/PROJECT.md`: pitch, stack, demo script, scope and owners. Set `process: light` only if exactly one person will work on the project; set `full` for two or more people. Set `gates: strict` only when the event lasts at least 3 days and at least 3 people will code; otherwise use `warn`. In warn mode, scope, claim and structure concerns are warnings and work continues. In strict mode, they block. Record the Plan owner as whoever led the interview; name Merger and Deputy only in strict mode. Replace the scope placeholders with the Must and Could headings, size them to the time remaining, and fill in `## Deadline and code freeze`. Then **delete the `UNCONFIGURED` line** at its top.
- `AGENTS.md`: replace `<Project name>` in the title.
- Scaffold the app with the stack's official starter into the repo, keeping it minimal. Do not overwrite the template files.
- `scripts/install`, `scripts/dev`, `scripts/lint`, `scripts/build`, `scripts/smoke`: replace each TODO line with the real command. `dev` must keep the `dotenvx run --` wrapper and the `PORT` variable. `smoke` must check the demo path and must not exit 1 any more when it passes.
- `.github/workflows/ci.yml`: add the language setup and dependency cache step. Leave the rest alone.
- `.gitignore`: add the stack's ignores.
- `.worktreelinks`: uncomment a dependency folder only if `docs/PARALLEL.md` says it is safe for this stack.
- Linter, formatter and test-runner configs: add `.worktrees/` to their ignore settings.
- `.env`: create it with the variable names from question 5 and empty values.
- `.github/workflows/ci.yml`: once the setup step is in, delete the `# KICKOFF:` comment block. `sh scripts/status` treats it as "CI not set up".
- Create the GitHub labels `task`, `ready`, `in-progress`, `needs-review` and `idea` with `gh label create ...`; ask once alongside the other approvals.
- `docs/STRUCTURE.md`: fill in the `<fill in at kickoff>` markers with the real folder layout for the stack.
- `.structure`: add an `allow` line for every top-level file and folder the scaffold created (for example `package.json`, `tsconfig.json`, `Dockerfile`, `src`, `tests`) and uncomment the placeholders. Add the stack's lockfiles to the `ignore` lines. Otherwise the first real PR fails `check-structure`. Change `max-lines` only if the team wants another limit.

## 3. Verify
Run `sh scripts/install`, `sh scripts/lint`, `sh scripts/build` and `sh scripts/smoke`. These are hard gates; fix failures before continuing. Create every scaffold file first, then run `sh scripts/check-structure`; structure concerns are warnings in `gates: warn` and block only in strict mode. Run `sh scripts/status` and note setup warnings, then continue. `check-scope` runs on every PR. In full mode, branches not named `issue-<N>-<slug>` fail the scope check, except `kickoff` while `docs/PROJECT.md` is `UNCONFIGURED`, and `revert-*` branches whose commits all start with `Revert`. In warn mode, note scope failures and continue; in strict mode, they block. Do not expose secrets.

## 4. Save
Create a branch `kickoff` and open a kickoff PR after the person leading agrees to proceed. Do not commit `.env.keys` or a plaintext `.env` with real values. In full mode, post this 10-line plan summary on the kickoff PR. By default, the Plan owner finalises the plan alone after discussing it with the team in person or in chat. Written agreement from every teammate is suggested only when the team is remote or someone disagrees.
1. Pitch and users: ...
2. Stack: ...
3. Demo step 1: ...
4. Demo step 2: ...
5. Demo step 3: ...
6. Must issues, each tied to a demo step: ...
7. Could issues: ...
8. Plan owner, and Merger and Deputy if strict: ...
9. Deadline and code freeze: ...
10. Process mode and team size: ...

When CI is green, anyone on the team may merge. Reviewer feedback is advice; do not hold up work for sign-off.

Until the kickoff reaches `main`, every agent still sees an unconfigured project, and new worktrees branch from `main`. Open a PR from `kickoff`, wait for CI, and merge when green; any teammate may merge.

## 5. Hand the rest to the humans
Print this list for the user. These need a person:
- [ ] One person (whoever ran kickoff) sets the real values in their own terminal: `dotenvx set KEY value` for each variable, then `dotenvx encrypt`, then commits the encrypted `.env`. Only one person creates the keys, so everyone shares the same `.env.keys`.
- [ ] Share `.env.keys` one person at a time, 1:1, with a timer. Not in a group chat.
- [ ] Make the hackathon repo public during the event (the template stays private). Enable secret scanning and push protection.
- [ ] GitHub settings: protect `main` by requiring a PR and the `ci` check. Reviews are optional; anyone on the team may merge when CI is green. Use squash merge.
- [ ] Protect the gates (strict gates only): add `.github/CODEOWNERS` naming two technical teammates for `scripts/`, `.github/`, `.structure`, `.scope-allow` and `docs/PROJECT.md`, and require code-owner review. GitHub does not let an author approve their own PR, so one owner on a two-person team can deadlock gate changes. Solo and two-person teams may skip required code-owner review.
- [ ] Each teammate runs `sh scripts/worktree new <N> <slug>` per issue.
- [ ] After the event, rotate every shared key.

In full mode, use the `docs/INTAKE.md` procedure and offer to draft the first GitHub issues from `docs/PROJECT.md`, with "Owner / files" filled in. Draft the shared-skeleton issue first (routes, layout and data model); mark every other issue "blocked by #N" for that issue. Create approved issues labelled `task` only. In strict mode, the Plan owner or Deputy adds `ready` after confirming the order and that the shared skeleton is merged. In warn mode, the agent may add `ready` after the person's yes.

## 6. Finish
Ask the user whether to delete this file. Keep the "First run" section of `AGENTS.md`: it makes every session run `sh scripts/status`. Delete `KICKOFF.md` on yes, and change the pointers to it in `AGENTS.md` and `scripts/status` to say "ask a teammate to re-run setup".
