# Where things go

The layout of this repo and the rules for adding to it. `sh scripts/check-structure` enforces the top-level names and line limit in `.structure`. Keep both in step with this page.

## Layout

```text
.
|-- .claude/        Claude Code adapters (optional)
|-- .github/        CI workflow, issue and PR templates
|-- docs/           Project docs
|-- scripts/        install, dev, lint, build, smoke, worktree, checks
|-- src/            FastAPI app and static assets, grouped by module
|-- tests/          not created yet; add focused smoke coverage as features land
`-- (root files)    AGENTS.md, CLAUDE.md, KICKOFF.md, README.md, .structure, config
```

## Where things go

- One purpose per file. If a file does two jobs or passes the `max-lines` limit in `.structure`, split it.
- Tests sit next to the code they test, or in a `tests/` folder that mirrors `src/`.
- Config files go in the root only if the tool needs them there.
- Python application code lives in `src/`; keep container and dependency config in the root.
- Nothing new in the repo root unless `.structure` allows it.
- Out-of-scope ideas become GitHub issues labelled `idea`.

## Changing the layout

Edit `.structure` and this file in the same PR. Ask the team before adding a top-level folder.
