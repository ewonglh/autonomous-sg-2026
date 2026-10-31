// Participant screen. Step 1: type the room code. Step 2: you see exactly what the presenter
// screen shows right now (a poll, a word cloud or a Q&A slide) and can answer it. One thing at a time.
import { codeFromPath, el, request, sessionPath, subscribe } from "./api.js";
import { loadQa, renderAskForm, renderQaList, toggleUpvote } from "./qa.js";
import { Countdown, secondsLeftOf } from "./timer.js";

const $ = (id) => document.getElementById(id);
const SAVED = "crowdpulse-joined-code";
let started = false;
let stopUpdates = null;
let onTimerDone = () => {};
const countdown = new Countdown($("timer"), () => onTimerDone());

const saved = (() => {
  try {
    return sessionStorage.getItem(SAVED);
  } catch {
    return null;
  }
})();
if (saved) start(saved);
else showCodeForm(codeFromPath());

function showCodeForm(prefill) {
  $("session").hidden = true;
  $("code-form").hidden = false;
  if (prefill) $("code-input").value = prefill.toUpperCase();
  $("code-input").focus();
}

$("code-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const value = $("code-input").value.trim().toUpperCase();
  if (!value) return;
  try {
    await request("GET", `${sessionPath(value)}/state`);
  } catch (err) {
    $("code-status").textContent = err.status === 404 ? "No session with that code. Check the screen and try again." : "Can't reach the session. Check your connection and try again.";
    return;
  }
  try {
    sessionStorage.setItem(SAVED, value);
  } catch {
    /* storage blocked: you stay joined until you reload */
  }
  start(value);
});

$("leave").addEventListener("click", () => {
  try {
    sessionStorage.removeItem(SAVED);
  } catch {
    /* nothing saved */
  }
  if (stopUpdates) stopUpdates();
  stopUpdates = null;
  started = false;
  countdown.set(null);
  $("activity").replaceChildren();
  $("code-input").value = "";
  $("code-status").textContent = "";
  document.title = "Join · CrowdPulse";
  showCodeForm(null);
});

// Remembers what this browser already sent, per question, so the screen survives a reload.
function sent(code, qid) {
  try {
    return JSON.parse(localStorage.getItem(`crowdpulse-sent-${code}-${qid}`)) || [];
  } catch {
    return [];
  }
}
function remember(code, qid, value) {
  try {
    localStorage.setItem(`crowdpulse-sent-${code}-${qid}`, JSON.stringify([...sent(code, qid), value]));
  } catch {
    /* storage blocked: fine, the server still rejects repeat votes */
  }
}

function start(code) {
  if (started) return;
  started = true;
  $("code-form").hidden = true;
  $("session").hidden = false;
  let lastKey = "";
  let qaList = null;
  let qaId = null;
  onTimerDone = () => refresh();

  async function refresh(type) {
    let state;
    try {
      state = await request("GET", `${sessionPath(code)}/state`);
    } catch (err) {
      if (err.status === 404) {
        $("activity").replaceChildren(el("p", { class: "error" }, "This session has ended."));
        return;
      }
      $("activity").replaceChildren(el("p", { class: "error" }, "Can't reach the session. Retrying…"));
      lastKey = "";
      return;
    }
    $("title").textContent = state.title || "CrowdPulse";
    document.title = `${state.title || "Join"} · CrowdPulse`;
    const q = state.active_question;
    countdown.set(secondsLeftOf(q));
    const isQa = q && q.type === "qa";
    // Only redraw when the slide changes, so typing is never interrupted.
    const key = !q ? "none" : isQa ? `qa:${q.id}:${q.is_open}` : `${q.id}:${q.is_open}:${sent(code, q.id).length}`;
    if (key !== lastKey) {
      lastKey = key;
      if (isQa) {
        qaList = el("div");
        qaId = q.id;
        const ask = q.is_open ? renderAskForm(code, q.id, () => refresh("qa_changed")) : el("p", { class: "muted" }, "New questions are closed. You can still upvote.");
        $("activity").replaceChildren(el("h2", {}, q.text), ask, qaList);
      } else {
        qaList = null;
        $("activity").replaceChildren(renderQuestion(code, q, () => { lastKey = ""; refresh(); }));
      }
    }
    if (qaList && type !== "question_changed") refreshQa();
  }

  async function refreshQa() {
    const target = qaList;
    try {
      const qid = qaId;
      const items = await loadQa(code, qid);
      target.replaceChildren(renderQaList(items, { onUpvote: async (item) => { await toggleUpvote(code, qid, item); refreshQa(); } }));
    } catch {
      target.replaceChildren(el("p", { class: "error" }, "Can't load questions. Retrying…"));
    }
  }

  stopUpdates = subscribe(code, refresh);
}

function renderQuestion(code, q, onDone) {
  if (!q) return el("p", { class: "muted" }, "You're in. Waiting for the host to start…");
  const heading = el("h2", {}, q.text);
  if (!q.is_open) return el("div", {}, heading, el("p", { class: "muted" }, "Voting is closed. Watch the screen for the results."));
  const already = sent(code, q.id);
  const status = el("p", { "aria-live": "polite" });
  const submit = async (body, remembered) => {
    try {
      await request("POST", `${sessionPath(code)}/questions/${q.id}/responses`, { body, participant: true });
      remember(code, q.id, remembered);
      onDone();
    } catch (err) {
      if (err.status === 409) { remember(code, q.id, remembered); onDone(); return; }
      status.className = "error";
      status.textContent = err.message;
    }
  };

  if (q.type === "multiple_choice") {
    if (already.length) {
      const picked = q.options.find((o) => o.id === already[0]);
      return el("div", {}, heading, el("p", { class: "success" }, `Vote sent${picked ? `: ${picked.label}` : ""}. Thanks!`));
    }
    return el("div", { class: "stack" }, heading, q.options.map((o) => el("button", { class: "choice", onclick: () => submit({ option_id: o.id }, o.id) }, o.label)), status);
  }

  // Word cloud: send as many answers as you like.
  const list = already.length ? el("p", { class: "success" }, `Sent: ${already.join(", ")}`) : null;
  const input = el("input", { maxlength: 40, placeholder: "Type a word", "aria-label": "Your answer", autocomplete: "off" });
  const form = el(
    "form",
    {
      class: "stack",
      onsubmit: (event) => {
        event.preventDefault();
        const text = input.value.trim();
        if (text) submit({ text }, text);
      },
    },
    input,
    el("button", { class: "primary", type: "submit" }, "Send"),
  );
  return el("div", { class: "stack" }, heading, list, form, status);
}
