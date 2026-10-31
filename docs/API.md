# API contract

All JSON lives under `/api`. Contract changes are agreed in their owning issues. Route stubs in `src/routes.py` return dummy data in these shapes until the real logic lands.

## Authentication

- Participants send an `X-Participant-Id` header: a random UUID kept in the browser. It limits casual duplicate votes; it is not proof of one vote per person.
- Host calls send `Authorization: Bearer <host_key>`.

## Endpoints

| Method and path | Who | Body | Returns |
| --- | --- | --- | --- |
| `POST /api/sessions` | anyone | `{title?}` | `{code, host_key}`. Title defaults to `Untitled session` and is limited to 120 characters. The host key is shown once; store only its hash. |
| `GET /api/sessions/{code}/state` | public | none | `{title, active_question: {id, type, text, options[{id,label}], is_open, results_visible, response_count, results, chart, time_limit, seconds_left, image_url} \| null}`. `results` is `null` until revealed; then it contains `options[{option_id,label,count}]` or `words[{word,count}]`. |
| `GET /api/sessions/{code}/questions` | host | none | `{active_question_id, questions: [{id, position, type, text, options[{id,label}], is_open, results_visible, response_count, chart, time_limit, seconds_left, image_url}]}`. Ordered by position. |
| `POST /api/sessions/{code}/questions` | host | `{type: "multiple_choice" \| "word_cloud" \| "qa", text, options[], chart?, time_limit?}` | `{id}` |
| `PATCH /api/sessions/{code}/questions/{qid}` | host | `{is_open?, results_visible?, chart?, time_limit?, text?, options?[]}`; options only change while the slide has no responses (else 409 `has_responses`) | `{ok}` |
| `PUT /api/sessions/{code}/questions/order` | host | `{question_ids: [3, 1, 2]}` | `{ok}`; 422 unless the list is exactly the session's question ids |
| `DELETE /api/sessions/{code}/questions/{qid}` | host | none | `{ok}`. Removes the slide with its options and responses, clears the screen if it was showing, renumbers the rest 1..N |
| `POST /api/sessions/{code}/active` | host | `{question_id}` | `{ok}` |
| `POST /api/sessions/{code}/questions/{qid}/responses` | participant | `{option_id \| text}` | `{ok}` |
| `GET /api/sessions/{code}/questions/{qid}/qa` | public (sends `X-Participant-Id` if it has one) | none | `{items: [{id, text, upvotes, upvoted_by_me}]}`, most upvoted first |
| `POST /api/sessions/{code}/questions/{qid}/qa` | participant | `{text}` (1–280 chars) | `{id}`; 400 if the slide is closed |
| `POST /api/sessions/{code}/questions/{qid}/qa/{id}/upvote` | participant | none | `{ok}`; 409 if this participant already upvoted |
| `DELETE /api/sessions/{code}/questions/{qid}/qa/{id}/upvote` | participant | none | `{ok}`; does nothing if they had not upvoted; 404 if the item does not exist |
| `PUT /api/sessions/{code}/questions/{qid}/image` | host | `{data_url}`: a base64 PNG, JPEG, GIF or WebP data URL, max 1.5 MB | `{ok}`; 413 if too big, 422 if not a real image |
| `DELETE /api/sessions/{code}/questions/{qid}/image` | host | none | `{ok}`; fine if there was no picture |
| `GET /api/sessions/{code}/questions/{qid}/image` | public | none | the picture bytes; 404 if the slide has none |
| `GET /api/sessions/{code}/results` | host | none | `{results: [{question_id, type, options?: [{option_id, label, count}], words?: [{word, count}]}]}` |
| `GET /api/sessions/{code}/export.csv` | host | none | CSV file; owned by the CSV issue |
| `WS /ws/{code}` | anyone | none | broadcasts `question_changed` after question creation, edits, or selection, and `results_changed` after accepted responses |
| `GET /healthz` | anyone | none | `{"status": "ok"}` |

Notes:

- `type` is `multiple_choice`, `word_cloud` or `qa`. `options` and `chart` are used for multiple choice only.
- `chart` is `bar` (default) or `donut`: how a poll's results are drawn. It is `null` for other types. Patching `chart` on a non-poll returns 404.
- Slides are ordered by `position`. New slides go to the end; `PUT .../questions/order` sets positions 1..N in the given order. `/results` lists slides in this order.
- A `qa` slide has no options. `is_open` means "accepting new audience questions"; `results_visible` is ignored. In `/results` it appears as `{question_id, type}` only; its audience questions come from the Q&A routes below.
- Q&A routes return 404 if `{qid}` is not a `qa` slide in this session (or the item is not on that slide). Each Q&A slide has its own list. Upvoting works even when the slide is closed. Text is stored and returned as plain text; screens must not render it as HTML.
- Timers: `time_limit` is whole seconds (5–3600) or `null` for no limit; send `null` in `PATCH` to remove it. `POST /active` on a timed slide opens it, hides its results (not for `qa`) and starts the countdown; calling it again restarts it. `PATCH {is_open: true}` on the showing timed slide also restarts it, and `PATCH {is_open: false}` stops it. `seconds_left` is whole seconds left, worked out on the server, or `null` when no timer runs. At zero the server closes the slide, reveals its results (a `qa` slide just stops taking questions) and broadcasts `question_changed`. Answers after that are refused like any closed slide (`403 closed`; Q&A posts get 400).
- Pictures: each slide can have one. `image_url` is `null` without one, otherwise a URL like `/api/sessions/{code}/questions/{qid}/image?v=2`. The `v` changes whenever the picture changes, so screens can cache it. Uploads are checked by their bytes, not just their label; SVG is refused because it can carry scripts. Upload and delete broadcast `question_changed`.
- A `qa` slide's `response_count` is the number of audience questions on it.
- The WebSocket also sends `{"type": "qa_changed"}` after a new Q&A question, an upvote or a removed upvote.
- Responses: a repeat vote for multiple choice is rejected (`already_responded`). Word cloud allows up to 3 responses per participant.
- Rejected answers on `POST .../responses` reply `{"detail": "<readable text>", "code": "<code>"}`. Clients should read `code` first and fall back to `detail`:

  | Situation | Status | `code` |
  | --- | --- | --- |
  | This person already voted | 409 | `already_responded` |
  | The slide is closed | 403 | `closed` |
  | Word limit reached | 429 | `limit_reached` |
  | Wrong kind of answer for the slide | 422 | `wrong_type` |
  | Slide not found in this session | 404 | `not_found` |
  | Option does not belong to the slide | 422 | `invalid_option` |

- Slide limits (422 if broken): question text is trimmed, 1 to 300 characters; poll options are trimmed, 2 to 10 of them, 1 to 100 characters each, no duplicates ignoring case.
- Host routes return 401 without a bearer key.
- After a WebSocket message, clients refetch `state`.
- The `{ok}` and `{id}` replies for write routes are the skeleton's choice; they were not specified in the issue.

## Pages

- `/host/{code}#key=<host_key>`
- `/join/{code}`
- `/present/{code}`

The host key lives only in the URL fragment, never in the participant link or QR code.

## CSV columns, in order

`session_code, question_order, question_type, question_text, answer, participant_id, submitted_at_utc, qa_upvotes` (the last is blank for now).

## Tables

- `sessions(id, code, host_key_hash, title, created_at, last_active_at, active_question_id)`
- `questions(id, session_id, position, type, text, chart, time_limit, closes_at, is_open, results_visible)`; `closes_at` is the UTC time a running timer ends, else null; `type` allows `qa`, `chart` is `bar`, `donut` or null.
- `options(id, question_id, position, label)`
- `responses(id, question_id, participant_id, option_id, text, created_at)`, with a unique `(question_id, participant_id)` for multiple choice only (a partial unique index where `option_id` is set).
- `question_images(question_id, media_type, data, version)`: one optional picture per slide.
- `qa_items(id, question_id, participant_id, text, created_at)`: audience questions on a Q&A slide.
- `qa_upvotes(qa_item_id, participant_id)`, unique per pair.

The schema is created on startup by `src/db.py`. The database file is `crowdpulse.db`, or the path in `DB_PATH`. Tables are only created when missing, so after a schema change delete your old `crowdpulse.db` (there is no automatic upgrade).

## Tests

`sh scripts/python -m unittest discover tests`
