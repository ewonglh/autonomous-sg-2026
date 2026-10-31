# CrowdPulse

CrowdPulse is an open source live polling app for event hosts and audiences. The first version is designed to run on one computer and share through a temporary Cloudflare Quick Tunnel.

## Requirements

- Docker Desktop with Docker Compose
- Git
- Git Bash on Windows (or a POSIX shell)
- dotenvx for `sh scripts/dev` (no secrets are needed by the scaffold)

## Start locally

```sh
docker compose up --build -d
```

Open <http://localhost:3000>. The scaffold currently serves a health page; host, participant, presenter, and polling flows are the next implementation work.

The `tunnel` service prints a temporary public URL in its logs:

```sh
docker compose logs -f tunnel
```

Quick Tunnel URLs change when the tunnel restarts and are intended for temporary demos. Stop the app with `docker compose down`. The named `app_data` volume is retained; do not use `docker compose down -v` if it contains responses.

For local development, install Python dependencies into this repo's `.venv` with `sh scripts/install`, then run `sh scripts/dev`. Set `PORT` to choose a local port; it defaults to 3000.

## Project demo

1. Host creates a session with a multiple choice question and a word cloud question.
2. Participants join on their phones and submit answers; the presenter displays live results.
3. Host closes voting, changes questions, reveals results, and downloads a CSV.

## Planned response export

The target CSV has one row per response with session code, question order and type, question text, choice or free-text answer, anonymous participant ID, and UTC submission time. Text cells must be protected against spreadsheet formula injection.

## Team

- LimZiJing: session, question, and response APIs
- duncanlau06: host, participant, and presenter screens
- ewonglh: packaging, CSV export, integration, and README

See [docs/PROJECT.md](docs/PROJECT.md) for the current scope, module owners, deadline status, and demo path.
