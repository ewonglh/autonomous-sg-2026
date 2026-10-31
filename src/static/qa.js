// Q&A slides: the audience asks questions and upvotes others. Each Q&A slide (a question with
// type "qa") has its own list. Backend endpoints are proposed in issue #19:
//   GET  /api/sessions/{code}/questions/{qid}/qa               -> {items: [{id, text, upvotes, upvoted_by_me}]}
//   POST /api/sessions/{code}/questions/{qid}/qa               -> {id}   body {text}
//   POST /api/sessions/{code}/questions/{qid}/qa/{id}/upvote   -> {ok}   409 if already upvoted
import { ApiError, el, request, sessionPath } from "./api.js";

export const QA_MAX_LENGTH = 280;

const qaPath = (code, qid) => `${sessionPath(code)}/questions/${qid}/qa`;

// Returns the items sorted by upvotes, or null when the server has no Q&A yet.
export async function loadQa(code, qid) {
  try {
    const data = await request("GET", qaPath(code, qid), { participant: true });
    return [...(data.items || [])].sort((a, b) => b.upvotes - a.upvotes || a.id - b.id);
  } catch (err) {
    if (err instanceof ApiError && (err.status === 404 || err.status === 405)) return null;
    throw err;
  }
}

export function askQuestion(code, qid, text) {
  return request("POST", qaPath(code, qid), { body: { text }, participant: true });
}

export function upvote(code, qid, id) {
  return request("POST", `${qaPath(code, qid)}/${id}/upvote`, { participant: true });
}

export function removeUpvote(code, qid, id) {
  return request("DELETE", `${qaPath(code, qid)}/${id}/upvote`, { participant: true });
}

// Upvotes, or takes the upvote back if this person already upvoted. Errors (e.g. a repeat) are ignored.
export async function toggleUpvote(code, qid, item) {
  try {
    await (item.upvoted_by_me ? removeUpvote : upvote)(code, qid, item.id);
  } catch {
    /* already in that state */
  }
}

// items: list from loadQa. onUpvote(item) is optional; without it the list is read-only.
export function renderQaList(items, { onUpvote, limit } = {}) {
  if (items === null) return el("p", { class: "muted" }, "Q&A is not switched on yet.");
  if (!items.length) return el("p", { class: "muted" }, "No questions yet. Be the first to ask.");
  const shown = limit ? items.slice(0, limit) : items;
  return el(
    "ul",
    { class: "qa" },
    shown.map((item) =>
      el(
        "li",
        {},
        onUpvote
          ? el(
              "button",
              {
                class: "votes",
                "aria-pressed": item.upvoted_by_me ? "true" : "false",
                "aria-label": item.upvoted_by_me ? `Remove your upvote, ${item.upvotes} so far` : `Upvote, ${item.upvotes} so far`,
                title: item.upvoted_by_me ? "Tap again to remove your upvote" : "Upvote",
                onclick: (event) => {
                  event.currentTarget.disabled = true;
                  onUpvote(item);
                },
              },
              `▲ ${item.upvotes}`,
            )
          : el("span", { class: "votes badge" }, `▲ ${item.upvotes}`),
        el("span", { class: "text" }, item.text),
      ),
    ),
  );
}

// A form for participants. Calls onSent after a question is accepted.
export function renderAskForm(code, qid, onSent) {
  const input = el("textarea", { rows: 2, maxlength: QA_MAX_LENGTH, placeholder: "Type your question", "aria-label": "Your question" });
  const status = el("p", { class: "muted", "aria-live": "polite" });
  return el(
    "form",
    {
      class: "stack",
      onsubmit: async (event) => {
        event.preventDefault();
        const text = input.value.trim();
        if (!text) return;
        try {
          await askQuestion(code, qid, text);
          input.value = "";
          status.className = "success";
          status.textContent = "Question sent.";
          onSent();
        } catch (err) {
          status.className = "error";
          status.textContent = err.status === 404 ? "Q&A is not switched on yet." : err.message;
        }
      },
    },
    input,
    el("button", { class: "primary", type: "submit" }, "Send question"),
    status,
  );
}
