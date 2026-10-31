# API contract

All JSON lives under `/api`. Any change to this contract is agreed on issue #4 first. Route stubs in `src/routes.py` return dummy data in these shapes until the real logic lands.

## Authentication

- Participants send an `X-Participant-Id` header: a random UUID kept in the browser. It limits casual duplicate votes; it is not proof of one vote per person.
- Host calls send `Authorization: Bearer <host_key>`.

## Endpoints

| Method and path | Who | Body | Returns |
| --- | --- | --- | --- |
| `POST /api/sessions` | anyone | none | `{code, host_key}`. The key is shown once; store only its hash. |
| `GET /api/sessions/{code}/state` | public | none | `{title, active_question: {id, type, text, options[{id,label}], is_open, results_visible} \| null}` |
| `POST /api/sessions/{code}/questions` | host | `{type: "multiple_choice" \| "word_cloud", text, options[]}` | `{id}` |
| `PATCH /api/sessions/{code}/questions/{qid}` | host | `{is_open?, results_visible?}` | `{ok}` |
| `POST /api/sessions/{code}/active` | host | `{question_id}` | `{ok}` |
| `POST /api/sessions/{code}/questions/{qid}/responses` | participant | `{option_id \| text}` | `{ok}` |
| `GET /api/sessions/{code}/results` | host | none | `{results: [{question_id, type, options?: [{option_id, label, count}], words?: [{word, count}]}]}` |
| `GET /api/sessions/{code}/export.csv` | host | none | CSV file; owned by the CSV issue |
| `WS /ws/{code}` | anyone | none | server sends `{"type": "question_changed"}` or `{"type": "results_changed"}` |
| `GET /healthz` | anyone | none | `{"status": "ok"}` |

Notes:

- `type` is `multiple_choice` or `word_cloud`. `options` is used for multiple choice only.
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
- `questions(id, session_id, position, type, text, is_open, results_visible)`
- `options(id, question_id, position, label)`
- `responses(id, question_id, participant_id, option_id, text, created_at)`, with a unique `(question_id, participant_id)` for multiple choice only (a partial unique index where `option_id` is set).

The schema is created on startup by `src/db.py`. The database file is `crowdpulse.db`, or the path in `DB_PATH`.

## Tests

`sh scripts/python -m unittest discover tests`
