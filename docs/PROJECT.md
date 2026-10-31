# CrowdPulse — agent context

Agents read this file for context. Keep the full build plan in the team's planning space; this is the short version everyone needs to work.

## Open items for the team

- [ ] Confirm the Plan owner (currently LimZiJing).
- [ ] Set the exact submission deadline and presentation time, then replace the placeholders under "Deadline and code freeze".
- [ ] Agree routes, JSON shapes and CSV columns before parallel work starts.

Plan owner: LimZiJing (assumed kickoff lead; confirm with team)
Merger: none (warn gates)
Deputy: none (warn gates)

## Process
<!-- Kickoff sets light only if exactly one person works on the project; otherwise full. -->
process: full

## Gates
<!-- warn = scope, claim and structure problems are warnings and work continues; strict = they block. Use strict only for events of 3+ days with 3+ coders. -->
gates: warn

## One-line pitch
An open source live polling app for event hosts and audiences: hosts run questions, participants answer on their phones, and presenters show live results.

## Stack
Python 3.12, FastAPI, SQLite, Docker Compose; local app shared through a Cloudflare Quick Tunnel.

## Demo script (the path that must never break)
1. Host opens a session and prepares a multiple choice question and a word cloud question.
2. Participants join from a phone with the public link or room code and submit answers; the presenter sees results update live.
3. Host closes voting, moves to the next question, reveals results, and downloads the response CSV.

## Deadline and code freeze
Submission deadline: confirm exact date and time with the team; build window is six hours.
Code freeze: 5 hours 15 minutes after the agreed start (last 45 minutes reserved for fixes and rehearsal).
Demo runs: during the event; confirm the presentation time with the team.

## Must have (each tied to a demo step)
- Step 1: host creates a session and multiple choice and word cloud questions; voting can be opened or closed.
- Step 2: participants join without accounts and answer on a phone; presenter shows the active question and live response count/results.
- Step 3: host changes questions, reveals results, and downloads responses as CSV.
- Host controls use a separate random private link; participant links and QR codes never expose it.
- Run locally in Docker Compose and share through a temporary Cloudflare Quick Tunnel; persist responses across app restarts.

## Could have (only after every Must is merged)
- QR code on the presenter screen; mobile layout polish.
- Q&A submissions with upvotes.

## Out of scope (cut on purpose)
- Accounts, passwords, and sign-in.
- Poll formats beyond multiple choice, word cloud, and the optional Q&A stretch goal.
- Poll Everywhere branding, assets, or a full feature-for-feature copy.

## Module owners
| Area | Owner |
|------|-------|
| Session, question, and response APIs | Member A — LimZiJing |
| Host, participant, and presenter UI | Member B — duncanlau06 |
| Packaging, CSV export, integration, and README | Member C — ewonglh |
