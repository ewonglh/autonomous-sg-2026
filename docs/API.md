# API contract

All JSON lives under `/api`. Contract changes are agreed in their owning issues. Route stubs in `src/routes.py` return dummy data in these shapes until the real logic lands.

## Authentication

- Participants send an `X-Participant-Id` header: a random UUID kept in the browser. It limits casual duplicate votes; it is not proof of one vote per person.
- Host calls send `Authorization: Bearer <host_key>`.

## Endpoints

| Method and path | Who | Body | Returns |
| --- | --- | --- | --- |
| `POST /api/sessions` | anyone | `{title?}` | `{code, host_key}`. Title defaults to `Untitled session` and is limited to 120 characters. The host key is shown once; store only its hash. |
| `GET /api/sessions/{code}/state` | public | none | `{title, active_question: {id, type, text, options[{id,label}], is_open, results_visible} \| null}` |
| `GET /api/sessions/{code}/questions` | host | none | `{active_question_id, questions: [{id, position, type, text, options[{id,label}], is_open, results_visible, response_count}]}`. Ordered by position. |
| `POST /api/sessions/{code}/questions` | host | `{type: "multiple_choice" \| "word_cloud", text, options[]}` | `{id}` |
| `PATCH /api/sessions/{code}/questions/{qid}` | host | `{is_open?, results_visible?}` | `{ok}` |
| `POST /api/sessions/{code}/active` | host | `{question_id}` | `{ok}` |
| `POST /api/sessions/{code}/questions/{qid}/responses` | participant | `{option_id \| text}` | `{ok}` |
| `GET /api/sessions/{code}/results` | host | none | `{results: [{question_id, type, options?: [{option_id, label, count}], words?: [{word, count}]}]}` |
| `GET /api/sessions/{code}/export.csv` | host | none | CSV file; owned by the CSV issue |
| `WS /ws/{code}` | anyone | none | broadcasts `question_changed` after question creation, edits, or selection, and `results_changed` after accepted responses |
| `GET /healthz` | anyone | none | `{"status": "ok"}` |

Notes:

- `type` is `multiple_choice` or `word_cloud`. `options` is used for multiple choice only.
- Responses: a repeat vote for multiple choice returns 409. Word cloud allows up to 3 responses per participant.
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
