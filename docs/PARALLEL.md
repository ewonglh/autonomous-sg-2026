# Working in parallel

Several people, each with an agent, working at once. This page is tool-neutral: it uses git, `gh` and the scripts, so any agent harness or model can follow it.

## 1. One worktree per issue

```sh
sh scripts/worktree new <issue-number> <slug>   # creates .worktrees/issue-<N>-<slug>
cd .worktrees/issue-<N>-<slug>
sh scripts/install
sh scripts/dev   # port 3000 + <N>, taken from the worktree name
```

- Worktrees sit inside the repo in `.worktrees/` (gitignored), branched from the latest remote default branch (`origin/<default>`), never from your local copy. The script also fast-forwards the local default branch, and warns instead of overwriting if it has commits of its own.
- Start your agent with that folder as its working directory. One agent session per worktree.
- Create worktrees from the main checkout (the script handles this). Never run `git worktree add` from inside another worktree.
- `.worktreeinclude` lists files copied into each worktree (for example `.env.keys`), one path per line.

## 2. Sharing dependencies across worktrees

### Shared files

- Lockfiles, route lists, and layout or data-model files are shared files.
- One skeleton issue creates the shared structure first; other issues touching it are `blocked by` the skeleton issue.
- Dependency changes belong in their own tiny issue, owned by one person (the Plan owner is the default), and must be merged first.
- After a lockfile conflict, rebase and run `sh scripts/install`; do not hand-merge the lockfile.

A worktree is a fresh checkout, so gitignored folders such as `node_modules` are missing. Options, cheapest first:

1. **Do nothing and let the toolchain find them (Node).** Node looks for `node_modules` in each parent folder in turn, so a worktree nested in the repo uses the main checkout's `node_modules` automatically (*established* Node behaviour). Two catches: CLI binaries in `node_modules/.bin` may not be on your path (run them through your package manager's run command; *unverified*), and a branch that changes dependencies silently tests against main's versions.
2. **Symlink a folder.** List it in `.worktreelinks`; `scripts/worktree new` links it. On Windows this needs Developer Mode and the script falls back with a message when symlinks are unavailable. Same catch as above: a branch that changes dependencies must remove the link and run its own install.
3. **Make a per-worktree install cheap.** Use a package manager with a shared cache: pnpm for Node (global store, hard links) or `uv` for Python (shared cache, one `.venv` per worktree). Both are *approximate* recommendations from memory; check their docs. Do not symlink a Python `.venv`: virtual environments record absolute paths.
4. **Nothing to do:** Go (global module cache). Rust shares downloaded crates, but build output (`target/`) is large and per worktree.

Not shared, whatever you do: ports (use `3000 + issue number`), local databases, Docker containers. Give each worktree its own.

## 3. Pitfalls of nesting worktrees inside the repo

- **Tools that scan the repo root can pick up `.worktrees/`**: linters, formatters, test runners, `tsc`. Add `.worktrees/` to their ignore or exclude settings at kickoff. Git and ripgrep already respect `.gitignore`.
- **Windows path length:** deep paths such as `.worktrees/issue-12-x/node_modules/...` can pass 260 characters. Run `git config core.longpaths true` and enable long paths in Windows.
- **Agents wandering:** an agent started at the repo root can read other worktrees. Start each agent inside its own worktree and tell it to stay there (this is in `AGENTS.md`).
- **Cleanup:** `sh scripts/worktree remove <N> <slug>` once the PR is merged, then delete the branch.

## 4. Orchestrator and workers

Two roles, defined in plain Markdown so any harness or model can follow them:

- [ORCHESTRATOR.md](ORCHESTRATOR.md): picks non-overlapping issues, starts workers, checks their PRs, reports to humans. Writes no code and never merges.
- [WORKER.md](WORKER.md): takes exactly one issue in its own worktree, opens one PR, reports back.

The orchestrator can be a human, or an agent session. Workers can be subagents of whatever harness you use, or separate agent sessions started by hand or by script in their own worktree. GitHub issues are the task queue and PRs are the results, so the roles do not depend on a harness feature.

`.claude/agents/` holds optional Claude Code adapters that point at these two files. Teammates on other tools ignore that folder.

## 5. Mixed agents and models

- Make issues small and explicit; weaker models need a clear goal, files and acceptance list.
- Do not trust an agent's claim that it works. `sh scripts/lint` and `sh scripts/smoke` are the judge.
- The PR template asks which agent and model produced the change, so you can see which setup is producing bad diffs.
