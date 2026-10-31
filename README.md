# CrowdPulse

CrowdPulse is an open source live polling app for event hosts and audiences. The first version is designed to run on one computer and share through a temporary Cloudflare Quick Tunnel.

## Prerequisites

- Docker Desktop (running) with Docker Compose
- Git, and Git Bash on Windows (or any POSIX shell)
- Optional, for `sh scripts/dev` only: Python 3 and dotenvx. No secrets are needed for the Docker demo.

## Start

```sh
docker compose up --build -d
```

Check it: open <http://localhost:3000/healthz>. It should return `{"status":"ok"}`.

Find the public link for phones:

```sh
docker compose logs tunnel
```

Look for a line containing `https://<random-words>.trycloudflare.com`. Add `/healthz` to test it. The link changes every time the tunnel restarts, so do not print or share it ahead of the event.

## Stop

```sh
docker compose down
```

The named volume `app_data` is set up for SQLite data. Responses will persist across `down` and `up` once the backend writes to it (issue #5).

## Troubleshooting

- `failed to connect to the docker API`: Docker Desktop is not running. Start it and wait for the whale icon to settle.
- Port 3000 already in use: stop whatever else uses it, or change the left-hand number in `compose.yaml` (`"127.0.0.1:3000:8000"`).
- No `trycloudflare.com` line in the logs: wait 10 seconds and run `docker compose logs tunnel` again. If still empty, run `docker compose restart tunnel` (this gives a new URL).
- Tunnel link does not load on mobile data: confirm `http://localhost:3000/healthz` works first, then restart the tunnel and use the new URL.
- App changes not showing: rebuild with `docker compose up --build -d`.
- Live updates stop working: run only one app container. The WebSocket manager is in memory.

## Local development

Install Python dependencies into this repo's `.venv` with `sh scripts/install`, then run `sh scripts/dev`. Set `PORT` to choose a local port; it defaults to 3000.

## Project demo

1. Host creates a session with a multiple choice question and a word cloud question.
2. Participants join on their phones and submit answers; the presenter displays live results.
3. Host closes voting, changes questions, reveals results, and downloads a CSV.

## Response export (CSV)

One row per response, UTF-8 with a byte order mark so Excel opens it correctly. Columns:

1. Session code
2. Question order
3. Question type (multiple choice or word cloud)
4. Question text
5. Answer (chosen option or free text)
6. Anonymous participant ID
7. Submitted at (UTC)

Text cells starting with `=`, `+`, `-` or `@` are prefixed so spreadsheets do not run them as formulas. The export is not built yet; the column list is the agreed target.

## Contributing

New teammates read `docs/START-HERE.md`, then for each GitHub issue run `sh scripts/worktree new <N> <slug>`. `AGENTS.md` has the rules.

## Team

- LimZiJing: session, question, and response APIs
- duncanlau06: host, participant, and presenter screens
- ewonglh: packaging, CSV export, integration, and README

See [docs/PROJECT.md](docs/PROJECT.md) for the current scope, module owners, deadline status, and demo path.

## Licence

MIT. See [LICENSE](LICENSE).
