# Plan: Build a Self-Hosted Poll Everywhere Style App in Six Hours

## Goal and scope

Build an original, open source Poll Everywhere style app that one person can run locally with Docker Compose and share through a temporary Cloudflare Quick Tunnel. This plan treats six hours as the build window and assumes the app should stay available during a six-hour event.

Use Poll Everywhere’s public workflow as a reference: a host creates questions, participants join from their phones, and results update on a presenter screen. Its current product has many more formats, including ranking, clickable images, competitions, and attendance; those are outside this first build. [Poll Everywhere feature overview](https://support.polleverywhere.com/pe2/key-features-)

### First version features

- **Host:** create a session, add multiple choice and word cloud questions, open or close voting, move to the next question, reveal results, and export responses to CSV.
- **Participant:** join with a link or room code, answer on a phone without an account, and see when the question changes.
- **Presenter:** show the active question, a QR code, response count, and live results.
- **Stretch goal:** Q&A submissions with upvotes. Build this only after the core flow works end to end.

Use your own name, layout, and graphics. Reproduce the interaction pattern rather than Poll Everywhere’s branding or assets.

## Skip host sign-in

Do not build accounts, passwords, or a sign-in screen. When the host creates a session, generate a separate, random host control link. The host opens that link to manage the session and download responses. Participants get a different public join link or room code.

Treat the control link as a private key: anyone who has it can control that session. Keep it out of the QR code and participant view. Put its random key in the URL fragment so the browser can send it in an authorization header without including it in the HTTP request URL or normal server access logs. Store only a hash of the key on the server. Add a basic limit on session creation and expire abandoned sessions.

This keeps setup to a click while protecting host controls from people who only have the participant link. The link is a bearer key, so it should stay private.

## Suggested build

Use **one FastAPI app, SQLite, and plain HTML/CSS/JavaScript**, packaged as one app container. Add a **cloudflared** container to the same Compose file.

~~~text
Participant phones → temporary trycloudflare.com URL → cloudflared → FastAPI → SQLite
                                                        ↘ WebSocket updates → presenter
~~~

This keeps setup small: no separate frontend build, Redis, or external database. Run **one app process** because the simple WebSocket connection manager lives in memory; FastAPI’s documentation notes that this approach only works in a single process. [FastAPI WebSockets guide](https://fastapi.tiangolo.com/advanced/websockets/)

Use WebSockets for live updates and reconnect by fetching the current question again. Cloudflare Tunnel supports WebSockets, while Quick Tunnels do **not** support server-sent events. [Cloudflare Tunnel FAQ](https://developers.cloudflare.com/cloudflare-one/faq/cloudflare-tunnels-faq/), [Quick Tunnel limits](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/)

## Split the work across three people

Agree on the API shape and response data in the first 15 minutes. That lets the frontend and backend proceed at the same time.

| Team member | Owns | Deliverables |
|---|---|---|
| **A — Backend and data** | FastAPI, SQLite, session and question APIs, random host control keys, response writes, WebSockets, CSV export endpoint | Working persistence, protected host actions, live events, and a downloadable response CSV |
| **B — Frontend** | Host, participant, and presenter pages | Create and control questions, join and vote on mobile, live results, QR code, and an Export CSV button |
| **C — Packaging and integration** | Dockerfile, Compose, environment template, tunnel setup, README, integration checklist, end-to-end troubleshooting | One-command startup, tunnel instructions, and a verified demo path |

### Coordination checkpoints

- **0:00–0:15:** agree on routes, JSON shapes, CSV columns, and the host link behavior.
- **0:15–2:30:** build in parallel. Member C gets the app container and local health page running while A and B work against the agreed API.
- **2:30:** integrate create → join → vote. Fix contract mismatches immediately.
- **2:30–4:30:** add live updates, word cloud display, and CSV download.
- **4:30:** test the complete flow locally, including CSV export.
- **4:30–5:15:** test the tunnel from a phone on cellular data and close any public admin path that does not require the host key.
- **5:15–6:00:** resolve the highest impact issue, finish README, and rehearse the demo.

If one person finishes early, have them help with the largest integration issue. Keep a single person responsible for merging each owned area to reduce conflicting edits.

## Six hour build plan

| Time | Work | Done when |
|---|---|---|
| **0:00–0:30** | Observe the public host, join, vote, and results flows. Write a one page feature checklist and sketch the three screens. Agree on API and CSV shape. | The team agrees on the exact MVP and ownership. |
| **0:30–1:15** | Create the repository, FastAPI app, static pages, SQLite schema, Dockerfile, compose.yaml, .env.example, MIT license, and README skeleton. | **docker compose up --build** serves a health page locally. |
| **1:15–2:15** | Build session creation with a private host control key, question creation, room codes, and active question controls. | Host can create a session with two questions and open the first. |
| **2:15–3:00** | Build the phone join page and multiple choice submission. Enforce one response per browser per question. | Two phones can join and vote; repeat submission does not add a vote. |
| **3:00–3:45** | Add presenter results and WebSocket events for votes and question changes. | Presenter counts update live; phones follow the active question. |
| **3:45–4:30** | Add word cloud responses and display, QR code, close/reveal controls, CSV export button and endpoint, and mobile layout. | The complete two question demo works and downloads a usable CSV. |
| **4:30–5:15** | Run the Quick Tunnel; test from a phone on cellular data. Add input limits, text escaping, basic rate limits, and host key checks. | Public participant flow works; host actions require the private control link. |
| **5:15–6:00** | Test restart and data persistence, run a small multi-user trial, finish README, fix the largest failure, and rehearse the demo. | A new person can follow setup instructions and run the demo. |

**Cut order if time slips:** Q&A → QR code → visual polish. Keep create → join → vote → live results → export intact.

## Build details, step by step

1. **Define the data.** Use tables for sessions, questions, options, and responses. Give each session a random, readable room code. Store question type, order, open/closed state, and whether results are visible. Add a database uniqueness rule on question_id plus participant_id for single-response questions. Generate a separate random host key per session; store only its hash.

2. **Create a small API.** Start with endpoints to create sessions and questions, change the active question, get the current question, submit a response, view protected results, and download protected CSV. Include a health endpoint at /healthz. Return a fresh state snapshot when a browser joins or reconnects. Require the host key for changes, results, and exports.

3. **Keep WebSockets simple.** Broadcast only events such as question_changed and results_changed. After an event, clients fetch the latest state. Put all writes through the HTTP API so validation happens in one place.

4. **Build three focused screens.** The host page creates questions and controls voting. The participant page has one clear answer action. The presenter page has large text, visible counts, and a QR code. Open the presenter through the **public tunnel URL** so the QR code points to the public join URL rather than localhost. Add an Export CSV action to the host page.

5. **Protect the public app.** Require the per-session host key for host actions. Keep it in the URL fragment or browser session storage and send it in an authorization header. Never put it in the participant join URL or QR code. Validate all inputs, set short limits for free text, render responses as text rather than HTML, and rate limit submissions. The browser identifier limits casual duplicate votes; it is **not** proof of one vote per person. Avoid collecting names, email addresses, or IP addresses for this event.

6. **Implement CSV export.** Make one row per response, with columns for session code, question order, question type, question text, choice label or free-text answer, anonymous participant ID, submission time in UTC, and Q&A upvote count if Q&A is added. Poll Everywhere offers downloadable CSV reports, including detailed response data; this first version can provide one simple raw response export. [Poll Everywhere report export guide](https://support.polleverywhere.com/pe2/creating-a-report-view-)

   Use a standard CSV writer so commas, quotes, and newlines are escaped correctly. Export UTF-8 with a byte order mark for smooth Excel opening. Protect spreadsheet users from formula injection by prefixing untrusted text cells that start with =, +, -, or @. Test the export with Unicode, commas, quotes, multiline text, empty results, and a response beginning with a formula character.

7. **Package it for one command setup.** A Compose file can build the app, persist SQLite in a named volume, bind the local test port to 127.0.0.1, and run cloudflared on the Compose network:

   ~~~yaml
   services:
     app:
       build: .
       env_file: .env
       ports:
         - "127.0.0.1:3000:8000"
       volumes:
         - app_data:/data

     tunnel:
       image: cloudflare/cloudflared:latest
       command: tunnel --url http://app:8000
       depends_on:
         - app

   volumes:
     app_data:
   ~~~

   In the finished repo, pin tested image and Python dependency versions. The app must listen on 0.0.0.0:8000 inside its container.

8. **Start and share it.** Run **docker compose up --build -d**, then **docker compose logs tunnel** to find the generated trycloudflare.com URL. Test the app locally at **http://localhost:3000**, then test the tunnel from a phone using cellular data. Cloudflare says a Quick Tunnel needs no account or domain, changes hostname when restarted, and stops working when cloudflared stops. It has no uptime guarantee and a limit of **200 in-flight requests**, so test with the expected audience before the event. [Cloudflare Quick Tunnels](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/)

9. **Finish the open source handoff.** Include README.md with prerequisites, setup, screenshots, the demo flow, CSV columns, data backup instructions, troubleshooting, and shutdown steps; plus LICENSE, .env.example, and a short contribution guide. Docker Desktop includes Compose on Windows, macOS, and Linux. [Docker Compose installation](https://docs.docker.com/compose/install/)

## Final acceptance check

Before the event, verify this path: fresh clone → create .env → **docker compose up --build -d** → host creates two questions → phone joins over the tunnel → vote appears live → host changes question → host downloads CSV → app restarts with responses still present. Test commas, quotes, emoji, and formula-like text in the CSV. Test a few simultaneous phones. Keep the computer awake and watch **docker compose logs -f app tunnel** during the event.

At the end, run **docker compose down** to close the public link while retaining the database volume. Avoid **docker compose down -v** unless you intend to delete stored responses; Docker documents that -v removes named volumes. [Docker Compose guide](https://docs.docker.com/compose/gettingstarted/)

