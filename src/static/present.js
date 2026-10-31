// Presenter screen for a projector. It only shows the active slide, exactly as the host set it up:
// a poll (bar or donut), a word cloud, or Q&A. Every phone shows the same slide.
// Results come from /state once the host reveals them (issue #11). Opened from the host screen,
// this page also has the host key in its fragment and can read /results directly.
import { chartOf, codeFromPath, el, hostKeyFromHash, request, sessionPath, subscribe } from "./api.js";
import { renderResults } from "./charts.js";
import { loadQa, renderQaList } from "./qa.js";
import { Countdown, secondsLeftOf } from "./timer.js";

const $ = (id) => document.getElementById(id);
const code = codeFromPath();
const hostKey = hostKeyFromHash();

$("join-url").textContent = `${location.host}/join`;
$("join-code").textContent = code;
const countdown = new Countdown($("timer"), () => refresh());

async function resultsFor(q) {
  if (q.results) return { ...q.results, words: q.results.words ?? (q.type === "word_cloud" ? [] : undefined) };
  if (!hostKey) return null;
  const data = await request("GET", `${sessionPath(code)}/results`, { hostKey });
  return data.results.find((r) => r.question_id === q.id) || null;
}

function countOf(q, result) {
  if (typeof q.response_count === "number") return q.response_count;
  if (!result) return null;
  return (result.options || result.words || []).reduce((sum, item) => sum + item.count, 0);
}

const plural = (n, word) => `${n} ${word}${n === 1 ? "" : "s"}`;

async function showQa(q) {
  const items = await loadQa(code, q.id).catch(() => []);
  $("count").textContent = [items ? plural(items.length, "question") : null, q.is_open ? "Ask yours on your phone" : "Questions closed"].filter(Boolean).join(" · ");
  $("results").replaceChildren(renderQaList(items, { limit: 8 }));
}

async function refresh() {
  let state;
  try {
    state = await request("GET", `${sessionPath(code)}/state`);
  } catch {
    $("count").textContent = "Reconnecting…";
    return;
  }
  document.title = `${state.title || "Present"} · CrowdPulse`;
  const q = state.active_question;
  countdown.set(secondsLeftOf(q));
  if (!q) {
    $("question").textContent = state.title || "Waiting for the host…";
    $("count").textContent = "";
    $("results").replaceChildren(el("p", { class: "muted" }, "Starting soon."));
    return;
  }
  $("question").textContent = q.text;
  if (q.type === "qa") return showQa(q);
  const result = await resultsFor(q).catch(() => null);
  const count = countOf(q, result);
  $("count").textContent = [count === null ? null : plural(count, "response"), q.is_open ? "Voting open" : "Voting closed"].filter(Boolean).join(" · ");
  if (!q.results_visible) {
    const when = secondsLeftOf(q) !== null ? "when the timer ends" : "when the host reveals them";
    $("results").replaceChildren(el("p", { class: "muted" }, `Results will appear ${when}.`));
    return;
  }
  $("results").replaceChildren(renderResults(result, chartOf(q)));
}

subscribe(code, refresh, 2000);
