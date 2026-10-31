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
|-- tests/          contract-shape tests (run: sh scripts/python -m unittest discover tests)
`-- (root files)    AGENTS.md, CLAUDE.md, KICKOFF.md, README.md, .structure, config
```

## Proposed API module layout

The current API skeleton uses `src/routes.py`, `src/db.py`, and `src/schemas.py`. As the later API issues add question control, responses, results, and live updates, use this target layout and move only the files owned by that issue:

```text
src/
  main.py
  auth.py
  db.py
  schemas.py
  events.py
  routes/
    sessions.py
    questions.py
    responses.py
    results.py
    live.py
  services/
    sessions.py
    questions.py
    responses.py
    results.py
  storage/
    sessions.py
    questions.py
    responses.py
    results.py
tests/
  support.py
  test_contract.py
  test_sessions.py
  test_questions.py
  test_question_state.py
  test_multiple_choice_responses.py
  test_word_cloud_responses.py
  test_results.py
  test_screen_api.py
```

`routes/` translates HTTP requests and responses, `services/` applies polling rules, `storage/` owns SQL queries, and `db.py` creates connections and the schema. Keep route handlers and service functions at one level of abstraction; add a shared helper when more than one feature needs the same behavior.

## Where things go

- One purpose per file. If a file does two jobs or passes the `max-lines` limit in `.structure`, split it.
- Tests sit next to the code they test, or in a `tests/` folder that mirrors `src/`.
- Config files go in the root only if the tool needs them there.
- Python application code lives in `src/`; keep container and dependency config in the root.
- Nothing new in the repo root unless `.structure` allows it.
- Out-of-scope ideas become GitHub issues labelled `idea`.

## Changing the layout

Edit `.structure` and this file in the same PR. Ask the team before adding a top-level folder.
