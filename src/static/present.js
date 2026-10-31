// Presenter screen for a projector. It only shows the active slide, exactly as the host set it up:
// a poll (bar or donut), a word cloud, or Q&A. Every phone shows the same slide.
// The presenter moves between slides with ← and → (or Page Up/Down on a clicker). That needs the
// host key, so open this screen with "Start presentation" on the host page.
// Results come from /state once the host reveals them (issue #11). Opened from the host screen,
// this page also has the host key in its fragment and can read /results directly.
import { chartOf, codeFromPath, el, hostKeyFromHash, request, sessionPath, subscribe } from "./api.js";
import { renderResults } from "./charts.js";
import { loadQa, renderQaList } from "./qa.js";
import { Countdown, secondsLeftOf } from "./timer.js";
import { loadSlides, showSlide } from "./slides.js";
import { imageOf, showImage, watchImage } from "./image.js";

const $ = (id) => document.getElementById(id);
const code = codeFromPath();
const hostKey = hostKeyFromHash();

$("join-url").textContent = `${location.host}/join`;
$("join-code").textContent = code;
// Scanning the QR opens this session's join link on the phone. It uses this page's own address, so
// open the presenter screen from the public tunnel link, not localhost. The host key never goes in it.
$("join-qr").src = `/join/${encodeURIComponent(code)}/qr.svg?origin=${encodeURIComponent(location.origin)}`;
$("join-qr").hidden = false;
const countdown = new Countdown($("timer"), () => refresh());
watchImage(code, () => refresh());

// ← → ↑ ↓ and Page Up/Down hop between slides. Held-down keys and fast clicks are ignored while a
// move is in progress, so the presenter never skips a slide by accident.
let moving = false;
const STEP = { ArrowRight: 1, ArrowDown: 1, PageDown: 1, ArrowLeft: -1, ArrowUp: -1, PageUp: -1 };
document.addEventListener("keydown", async (event) => {
  const delta = STEP[event.key];
  if (!delta || !hostKey || event.ctrlKey || event.metaKey || event.altKey) return;
  event.preventDefault();
  if (moving) return;
  moving = true;
  try {
    const { list, active } = await loadSlides(code, hostKey);
    const index = list.findIndex((q) => q.id === active);
    const target = index === -1 ? (delta > 0 ? list[0] : null) : list[index + delta];
    if (target) await showSlide(code, hostKey, target.id);
  } catch {
    /* the next refresh shows the real state */
  } finally {
    moving = false;
    refresh();
  }
});

// The slide's number ("3") in the top-right corner, only on the presenter's own screen.
async function showSlideNumber() {
  if (!hostKey) return;
  try {
    const { list, active } = await loadSlides(code, hostKey);
    const index = list.findIndex((q) => q.id === active);
    $("slide-number").hidden = index === -1;
    $("slide-number").textContent = String(index + 1);
  } catch {
    $("slide-number").hidden = true;
  }
}

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
  showSlideNumber();
  countdown.set(secondsLeftOf(q));
  showImage($("slide-image"), imageOf(code, q));
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
