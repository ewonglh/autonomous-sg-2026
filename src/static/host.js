// Host console: create a session, set up slides (poll with bar or donut, word cloud, Q&A),
// put them in order, step through them, watch results, export CSV.
import { ApiError, chartOf, codeFromPath, el, hostKeyFromHash, request, sessionPath, subscribe } from "./api.js";
import { renderResults } from "./charts.js";
import { loadQa, renderQaList } from "./qa.js";
import { Countdown, limitLabel, secondsLeftOf, TIME_LIMITS } from "./timer.js";
import { imageOf, saveImage, shrinkImage, uploadImage } from "./image.js";

const $ = (id) => document.getElementById(id);
const code = codeFromPath();
const hostKey = hostKeyFromHash();
const TYPE_LABEL = { multiple_choice: "Poll", word_cloud: "Word cloud", qa: "Q&A" };
const PLACEHOLDER = { multiple_choice: "Which talk should we extend?", word_cloud: "One word for this quarter?", qa: "Ask the leadership team anything" };
let slides = [];
let activeId = null;
let lastListKey = "";
let countdown = null;

if (!code) showCreate();
else if (!hostKey) $("no-key").hidden = false;
else start();

function showCreate() {
  $("create").hidden = false;
  $("create").addEventListener("submit", async (event) => {
    event.preventDefault();
    const title = $("title-input").value.trim();
    try {
      const created = await request("POST", "/api/sessions", { body: title ? { title } : {} });
      location.replace(`/host/${encodeURIComponent(created.code)}#key=${encodeURIComponent(created.host_key)}`);
    } catch (err) {
      $("create-status").textContent = `Could not create a session: ${err.message}`;
    }
  });
}

// Slides come from GET /questions (issue #11). Until that exists, keep a local copy.
const localKey = `crowdpulse-host-${code}`;
function localSlides() {
  try {
    return JSON.parse(localStorage.getItem(localKey)) || [];
  } catch {
    return [];
  }
}
function saveLocal(list) {
  try {
    localStorage.setItem(localKey, JSON.stringify(list));
  } catch {
    /* storage blocked */
  }
}
function patchLocal(id, changes) {
  saveLocal(localSlides().map((q) => (q.id === id ? { ...q, ...changes } : q)));
}
const notFound = (err) => err instanceof ApiError && [404, 405].includes(err.status);
const byPosition = (list) => [...list].sort((a, b) => (a.position ?? 0) - (b.position ?? 0));

async function loadSlides() {
  try {
    const data = await request("GET", `${sessionPath(code)}/questions`, { hostKey });
    return { list: byPosition(data.questions), active: data.active_question_id };
  } catch (err) {
    if (!notFound(err)) throw err;
    const state = await request("GET", `${sessionPath(code)}/state`);
    const a = state.active_question;
    const list = localSlides().map((q) => (a && q.id === a.id ? { ...q, is_open: a.is_open, results_visible: a.results_visible } : q));
    return { list: byPosition(list), active: a ? a.id : null };
  }
}

function start() {
  $("console").hidden = false;
  const joinUrl = `${location.origin}/join/${encodeURIComponent(code)}`;
  $("code").textContent = code;
  $("join-link").value = joinUrl;
  $("copy-join").onclick = async () => {
    try {
      await navigator.clipboard.writeText(joinUrl);
      say("Join link copied.");
    } catch {
      $("join-link").select();
    }
  };
  // The presenter runs on the host's own screen, so it may carry the key in its fragment.
  $("open-present").onclick = () => window.open(`/present/${encodeURIComponent(code)}#key=${encodeURIComponent(hostKey)}`, "_blank", "noopener");
  $("export").onclick = exportCsv;
  $("prev").onclick = () => step(-1);
  $("next").onclick = () => step(1);
  $("add").addEventListener("submit", addSlide);
  $("q-type").addEventListener("change", typeChanged);
  $("q-time").replaceChildren(...timeOptions(0));
  countdown = new Countdown($("timer"), () => refresh());
  typeChanged();
  request("GET", `${sessionPath(code)}/state`).then((s) => {
    $("title").textContent = s.title || "Session";
    document.title = `${s.title || "Host"} · CrowdPulse`;
  }).catch(() => {});
  subscribe(code, refresh);
}

// Each slide can have a picture that shows to the right of its question on the presenter screen.
function imageNote(text, isError = false) {
  $("image-status").hidden = !text;
  $("image-status").className = isError ? "error" : "muted";
  $("image-status").textContent = text;
}

// file = a File to set, or null to remove the picture. Returns true when it worked.
async function setSlideImage(id, file) {
  try {
    const dataUrl = file ? await shrinkImage(file) : null;
    if (!saveImage(code, id, dataUrl)) throw new Error("This browser would not save the image. Try a smaller one.");
    await uploadImage(code, id, hostKey, dataUrl);
    imageNote(file ? "Picture saved for that slide." : "Picture removed.");
    return true;
  } catch (err) {
    imageNote(err.message, true);
    return false;
  } finally {
    lastListKey = "";
    refresh();
  }
}

function say(text, isError = false) {
  $("share-status").className = isError ? "error" : "success";
  $("share-status").textContent = text;
}

function typeChanged() {
  const type = $("q-type").value;
  $("poll-fields").hidden = type !== "multiple_choice";
  $("q-text-label").textContent = type === "qa" ? "Prompt shown on screen" : "Question";
  $("q-text").placeholder = PLACEHOLDER[type];
}

async function addSlide(event) {
  event.preventDefault();
  const type = $("q-type").value;
  const text = $("q-text").value.trim();
  const options = type === "multiple_choice" ? $("q-options").value.split("\n").map((s) => s.trim()).filter(Boolean) : [];
  const status = $("add-status");
  if (type === "multiple_choice" && options.length < 2) {
    status.className = "error";
    status.textContent = "Add at least two options, one per line.";
    return;
  }
  const body = { type, text, options, time_limit: Number($("q-time").value) || null, ...(type === "multiple_choice" ? { chart: $("q-chart").value } : {}) };
  try {
    const { id } = await request("POST", `${sessionPath(code)}/questions`, { body, hostKey });
    const local = localSlides();
    saveLocal([...local, { ...body, id, options: options.map((label, i) => ({ id: i + 1, label })), is_open: false, results_visible: false, position: local.length + 1 }]);
    const picture = $("q-image").files[0];
    $("q-text").value = "";
    $("q-options").value = "";
    $("q-image").value = "";
    status.className = "success";
    status.textContent = `Slide ${slides.length + 1} added.`;
    if (picture) await setSlideImage(id, picture);
    else refresh();
  } catch (err) {
    status.className = "error";
    status.textContent =
      err.status === 422 && type !== "multiple_choice" && /type/i.test(err.message)
        ? `The server can't make ${TYPE_LABEL[type]} slides yet (backend issue #25). Polls work.`
        : err.message;
  }
}

async function act(path, method, body, localChanges) {
  try {
    await request(method, `${sessionPath(code)}${path}`, { body, hostKey });
    if (localChanges) patchLocal(localChanges.id, localChanges.changes);
  } catch (err) {
    say(err.message, true);
  }
  await refresh();
}

// Voting is automatic: the server opens a slide when it goes on screen, keeps it open while it is
// there (until its timer ends, if it has one) and closes it when another slide replaces it.
async function show(id) {
  await act("/active", "POST", { question_id: id });
  const status = $("run-status");
  status.className = activeId === id ? "" : "error";
  status.textContent = activeId === id ? "" : "The server accepted that but didn't change the slide on screen. It isn't saving the active slide yet (backend issue #5).";
}

function timeOptions(current) {
  return TIME_LIMITS.map((s) => el("option", { value: s, selected: s === (current || 0) }, limitLabel(s)));
}

function step(delta) {
  const index = slides.findIndex((q) => q.id === activeId);
  const next = slides[index === -1 ? 0 : index + delta];
  if (next) show(next.id);
}

// Moves a slide up (-1) or down (+1) and saves the new order.
async function move(index, delta) {
  const ids = slides.map((q) => q.id);
  [ids[index], ids[index + delta]] = [ids[index + delta], ids[index]];
  try {
    await request("PUT", `${sessionPath(code)}/questions/order`, { body: { question_ids: ids }, hostKey });
  } catch (err) {
    if (!notFound(err)) return say(err.message, true);
  }
  saveLocal(localSlides().map((q) => ({ ...q, position: ids.indexOf(q.id) + 1 })));
  refresh();
}

function slideItem(q, index) {
  const isActive = q.id === activeId;
  const patch = (changes) => act(`/questions/${q.id}`, "PATCH", changes, { id: q.id, changes });
  const toggle = (field, on, off) => el("button", { onclick: () => patch({ [field]: !q[field] }) }, q[field] ? off : on);
  const chartPicker =
    q.type === "multiple_choice"
      ? el(
          "select",
          { "aria-label": "Show results as", onchange: (event) => patch({ chart: event.target.value }) },
          el("option", { value: "bar", selected: chartOf(q) === "bar" }, "Bar chart"),
          el("option", { value: "donut", selected: chartOf(q) === "donut" }, "Donut chart"),
        )
      : null;
  const picture = imageOf(code, q);
  const pictureInput = el("input", { type: "file", accept: "image/*", hidden: true, onchange: (event) => { const file = event.target.files[0]; event.target.value = ""; if (file) setSlideImage(q.id, file); } });
  const count = typeof q.response_count === "number" ? el("span", { class: "muted" }, q.type === "qa" ? `${q.response_count} questions` : `${q.response_count} responses`) : null;
  return el(
    "li",
    { class: isActive ? "active" : "" },
    el(
      "div",
      { class: "row" },
      el("span", { class: "slide-num" }, String(index + 1)),
      el("strong", { class: "slide-text" }, q.text),
      picture ? el("img", { class: "image-thumb", src: picture, alt: "Picture for this slide" }) : null,
      el("span", { class: "badge" }, TYPE_LABEL[q.type] || q.type),
      isActive ? el("span", { class: "badge on" }, `On screen · ${q.type === "qa" ? "questions" : "voting"} ${q.is_open ? "open" : "closed"}`) : null,
    ),
    el(
      "div",
      { class: "row", style: "margin-top:8px" },
      el("button", { "aria-label": "Move up", title: "Move up", disabled: index === 0, onclick: () => move(index, -1) }, "↑"),
      el("button", { "aria-label": "Move down", title: "Move down", disabled: index === slides.length - 1, onclick: () => move(index, 1) }, "↓"),
      isActive ? null : el("button", { class: "primary", onclick: () => show(q.id) }, "Show"),
      isActive && q.time_limit ? el("button", { onclick: () => show(q.id) }, "Restart timer") : null,
      q.type === "qa" ? null : toggle("results_visible", "Reveal results", "Hide results"),
      chartPicker,
      el("label", { class: "button" }, picture ? "Change picture" : "Add picture", pictureInput),
      picture ? el("button", { onclick: () => setSlideImage(q.id, null) }, "Remove picture") : null,
      el("select", { "aria-label": "Time limit", onchange: (event) => patch({ time_limit: Number(event.target.value) || null }) }, timeOptions(q.time_limit)),
      count,
    ),
  );
}

async function refresh() {
  try {
    const loaded = await loadSlides();
    slides = loaded.list;
    activeId = loaded.active;
    // Redraw the list only when something changed, so an open dropdown is not closed.
    const listKey = JSON.stringify([slides, activeId], (k, v) => (k === "seconds_left" ? undefined : v));
    if (listKey !== lastListKey) {
      lastListKey = listKey;
      $("questions").replaceChildren(...(slides.length ? slides.map(slideItem) : [el("li", { class: "muted" }, "No slides yet. Add one below.")]));
    }
    const index = slides.findIndex((q) => q.id === activeId);
    const active = slides[index];
    $("now-showing").textContent = active ? `On screen: ${index + 1} of ${slides.length} · ${active.text}` : "Nothing on screen yet";
    countdown.set(secondsLeftOf(active));
    $("prev").disabled = index <= 0;
    $("next").disabled = index >= slides.length - 1 || !slides.length;
    $("next").textContent = index === -1 ? "Start ▶" : "Next ▶";
    await renderLive(active);
  } catch (err) {
    $("live").replaceChildren(el("p", { class: "error" }, err.status === 401 ? "Host key not accepted." : "Can't reach the server. Retrying…"));
  }
}

async function renderLive(active) {
  if (!active) {
    $("live").replaceChildren(el("p", { class: "muted" }, "Press Start to put slide 1 on screen."));
    return;
  }
  if (active.type === "qa") {
    const items = await loadQa(code, active.id).catch(() => []);
    $("live").replaceChildren(renderQaList(items));
    return;
  }
  const data = await request("GET", `${sessionPath(code)}/results`, { hostKey });
  $("live").replaceChildren(renderResults(data.results.find((r) => r.question_id === active.id), chartOf(active)));
}

async function exportCsv() {
  try {
    const blob = await request("GET", `${sessionPath(code)}/export.csv`, { hostKey });
    const url = URL.createObjectURL(blob);
    const link = el("a", { href: url, download: `crowdpulse-${code}.csv` });
    document.body.append(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  } catch (err) {
    say(`Export failed: ${err.message}`, true);
  }
}
