// Host setup page: create a session, set up slides (poll with bar or donut, word cloud, Q&A) with
// their time limit and picture, put them in order, then start the presentation. During the
// presentation the host only uses the projector screen (present.js); this page is not needed.
import { chartOf, codeFromPath, el, hostKeyFromHash, request, sessionPath, subscribe } from "./api.js";
import { limitLabel, TIME_LIMITS } from "./timer.js";
import { imageOf, saveImage, shrinkImage, uploadImage } from "./image.js";
import { byPosition, loadSlides, localSlides, notFound, patchLocal, saveLocal, showSlide } from "./slides.js";
import { renderLiveDashboard, renderResultsDashboard, setupHostDashboard } from "./host-dashboard.js";
import { watchPublicLink } from "./public-link.js";
import { setupDeckControls } from "./decks.js";

const $ = (id) => document.getElementById(id);
const code = codeFromPath();
const hostKey = hostKeyFromHash();
const TYPE_LABEL = { multiple_choice: "Poll", word_cloud: "Word cloud", qa: "Q&A" };
const PLACEHOLDER = { multiple_choice: "Which talk should we extend?", word_cloud: "One word for this quarter?", qa: "Ask the leadership team anything" };
let slides = [];
let activeId = null;
let activeQuestion = null;
let dashboard;
const publicLink = watchPublicLink(code, $("join-link"));

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

function start() {
  $("console").hidden = false;
  dashboard = setupHostDashboard((tab) => tab === "results" && refreshResults());
  const joinUrl = publicLink.enabled && !publicLink.origin
    ? "Finding the public link…"
    : `${publicLink.origin || location.origin}/join/${encodeURIComponent(code)}`;
  $("code").textContent = code;
  $("join-link").value = joinUrl;
  $("copy-join").onclick = async () => {
    if (publicLink.enabled && !publicLink.origin) return say("The public link is still starting. Try again in a moment.", true);
    try {
      await navigator.clipboard.writeText($("join-link").value);
      say("Join link copied.");
    } catch {
      $("join-link").select();
    }
  };
  $("start").onclick = startPresentation;
  $("export").onclick = exportCsv;
  setupDeckControls({ code, hostKey, getSlides: () => slides, onLoaded: refresh });
  enableDragReorder($("questions"));
  $("add").addEventListener("submit", addSlide);
  $("q-type").addEventListener("change", typeChanged);
  $("q-time").replaceChildren(...timeOptions(0));
  typeChanged();
  request("GET", `${sessionPath(code)}/state`).then((s) => {
    $("title").textContent = s.title || "Session";
    document.title = `${s.title || "Host"} · CrowdPulse`;
  }).catch(() => {});
  refresh();
  subscribe(code, (type) => {
    if (["question_changed", "results_changed", "qa_changed"].includes(type)) refresh();
    else if (type === "poll") refresh({ updateSlides: false });
  }, 3000);
}

function say(text, isError = false) {
  $("share-status").className = isError ? "error" : "success";
  $("share-status").textContent = text;
}

// Opens the projector screen (it carries the host key so ← and → can move between slides).
// Slide 1 goes on screen first if nothing is showing yet.
async function startPresentation() {
  if (!slides.length) return say("Add at least one slide first.", true);
  const path = `/present/${encodeURIComponent(code)}#key=${encodeURIComponent(hostKey)}`;
  if (publicLink.origin || !publicLink.enabled) {
    window.open(`${publicLink.origin || location.origin}${path}`, "_blank", "noopener");
  } else {
    const presenter = window.open("about:blank", "_blank");
    if (!presenter) return say("Allow pop-ups to open the presenter screen.", true);
    presenter.opener = null;
    say("Connecting to the public link…");
    const origin = await publicLink.wait(30000);
    if (!origin) {
      presenter.close();
      return say("The public link did not start. Check that Docker is running.", true);
    }
    presenter.location.replace(`${origin}${path}`);
  }
  try {
    if (activeId === null) await showSlide(code, hostKey, slides[0].id);
    say("Presenter opened. You can also control the live slide here.");
  } catch (err) {
    say(err.message, true);
  }
  refresh();
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
    const local = localSlides(code);
    saveLocal(code, [...local, { ...body, id, options: options.map((label, i) => ({ id: i + 1, label })), is_open: false, results_visible: false, position: local.length + 1 }]);
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

// Each slide can have a picture that shows to the right of its question on the projector.
function imageNote(text, isError = false) {
  $("image-status").hidden = !text;
  $("image-status").className = isError ? "error" : "muted";
  $("image-status").textContent = text;
}

// file = a File to set, or null to remove the picture.
async function setSlideImage(id, file) {
  try {
    const dataUrl = file ? await shrinkImage(file) : null;
    if (!saveImage(code, id, dataUrl)) throw new Error("This browser would not save the image. Try a smaller one.");
    await uploadImage(code, id, hostKey, dataUrl);
    imageNote(file ? "Picture saved for that slide." : "Picture removed.");
  } catch (err) {
    imageNote(err.message, true);
  } finally {
    refresh();
  }
}

async function patchSlide(id, changes) {
  try {
    await request("PATCH", `${sessionPath(code)}/questions/${id}`, { body: changes, hostKey });
    patchLocal(code, id, changes);
  } catch (err) {
    say(err.message, true);
  }
  refresh();
}

async function activateSlide(id) {
  if (id === undefined || id === null) return;
  try {
    await showSlide(code, hostKey, id);
  } catch (err) {
    return say(err.message, true);
  }
  refresh();
}

function timeOptions(current) {
  return TIME_LIMITS.map((s) => el("option", { value: s, selected: s === (current || 0) }, limitLabel(s)));
}

// Moves the slide at position `from` to position `to` (both 0-based) and saves the new order.
async function moveTo(from, to) {
  const ids = slides.map((q) => q.id);
  ids.splice(to, 0, ids.splice(from, 1)[0]);
  try {
    await request("PUT", `${sessionPath(code)}/questions/order`, { body: { question_ids: ids }, hostKey });
  } catch (err) {
    if (!notFound(err)) return say(err.message, true);
  }
  saveLocal(code, localSlides(code).map((q) => ({ ...q, position: ids.indexOf(q.id) + 1 })));
  refresh();
}

// Press and hold a slide (about half a second), then drag it to its place in the queue.
// Works with a mouse or a finger. A quick click or tap, or pressing a button, behaves as usual.
const HOLD_MS = 450;
function enableDragReorder(list) {
  list.addEventListener("pointerdown", (event) => {
    const item = event.target.closest("li[data-index]");
    if (!item || (event.pointerType === "mouse" && event.button !== 0)) return;
    if (event.target.closest("button, select, input, textarea, label, a")) return;
    const from = Number(item.dataset.index);
    const startY = event.clientY;
    const startScroll = window.scrollY;
    let lastY = startY;
    let to = from;
    let state = "waiting"; // waiting -> dragging -> done
    const items = () => [...list.querySelectorAll("li[data-index]")];
    const others = () => items().filter((li) => li !== item);
    const stopScroll = (e) => e.preventDefault();

    // Where the slide would land: before the first other slide whose middle is below the pointer.
    const markDrop = () => {
      items().forEach((li) => li.classList.remove("drop-above", "drop-below"));
      const rest = others();
      const found = rest.findIndex((li) => lastY < li.getBoundingClientRect().top + li.offsetHeight / 2);
      to = found === -1 ? rest.length : found;
      if (to === from) return;
      if (to < rest.length) rest[to].classList.add("drop-above");
      else rest[rest.length - 1].classList.add("drop-below");
    };
    // Moves the slide with the pointer and shows where it would land.
    const place = () => {
      item.style.transform = `translateY(${lastY - startY + (window.scrollY - startScroll)}px)`;
      markDrop();
    };
    const follow = () => {
      if (state !== "dragging") return;
      // Keep the page scrolling while the slide is held near its top or bottom edge.
      if (lastY < 70) window.scrollBy(0, -12);
      else if (lastY > window.innerHeight - 70) window.scrollBy(0, 12);
      place();
      requestAnimationFrame(follow);
    };
    const begin = () => {
      state = "dragging";
      item.classList.add("dragging");
      document.body.classList.add("reordering");
      try {
        item.setPointerCapture(event.pointerId);
      } catch {
        /* pointer already gone */
      }
      document.addEventListener("touchmove", stopScroll, { passive: false });
      follow();
    };
    const move = (e) => {
      lastY = e.clientY;
      if (state === "waiting" && Math.abs(e.clientY - startY) > 8) finish(false); // it is a scroll, not a drag
      else if (state === "dragging") place();
    };
    const up = () => finish(true);
    const cancel = () => finish(false);
    const blockMenu = (e) => e.preventDefault(); // a long press on a phone would open a menu
    const timer = setTimeout(begin, HOLD_MS);

    function finish(drop) {
      clearTimeout(timer);
      document.removeEventListener("pointermove", move);
      document.removeEventListener("pointerup", up);
      document.removeEventListener("pointercancel", cancel);
      document.removeEventListener("touchmove", stopScroll);
      document.removeEventListener("contextmenu", blockMenu);
      if (state === "dragging") {
        item.classList.remove("dragging");
        item.style.transform = "";
        items().forEach((li) => li.classList.remove("drop-above", "drop-below"));
        document.body.classList.remove("reordering");
        if (drop && to !== from) moveTo(from, to);
      }
      state = "done";
    }
    document.addEventListener("pointermove", move);
    document.addEventListener("pointerup", up);
    document.addEventListener("pointercancel", cancel);
    document.addEventListener("contextmenu", blockMenu);
  });
}

function slideItem(q, index) {
  const picture = imageOf(code, q);
  const pictureInput = el("input", { type: "file", accept: "image/*", hidden: true, onchange: (event) => { const file = event.target.files[0]; event.target.value = ""; if (file) setSlideImage(q.id, file); } });
  const chartPicker =
    q.type === "multiple_choice"
      ? el(
          "select",
          { "aria-label": "Show results as", onchange: (event) => patchSlide(q.id, { chart: event.target.value }) },
          el("option", { value: "bar", selected: chartOf(q) === "bar" }, "Bar chart"),
          el("option", { value: "donut", selected: chartOf(q) === "donut" }, "Donut chart"),
        )
      : null;
  return el(
    "li",
    { class: q.id === activeId ? "active" : "", "data-index": String(index) },
    el(
      "div",
      { class: "row" },
      el("span", { class: "slide-num" }, String(index + 1)),
      el("strong", { class: "slide-text" }, q.text),
      picture ? el("img", { class: "image-thumb", src: picture, alt: "Picture for this slide" }) : null,
      el("span", { class: "badge" }, TYPE_LABEL[q.type] || q.type),
      q.id === activeId ? el("span", { class: "badge on" }, "On screen") : null,
    ),
    el(
      "div",
      { class: "row", style: "margin-top:8px" },
      el("button", { disabled: q.id === activeId, onclick: () => activateSlide(q.id) }, q.id === activeId ? "On screen" : "Show slide"),
      el("button", { "aria-label": "Move up", title: "Move up", disabled: index === 0, onclick: () => moveTo(index, index - 1) }, "↑"),
      el("button", { "aria-label": "Move down", title: "Move down", disabled: index === slides.length - 1, onclick: () => moveTo(index, index + 1) }, "↓"),
      chartPicker,
      el("select", { "aria-label": "Time limit", onchange: (event) => patchSlide(q.id, { time_limit: Number(event.target.value) || null }) }, timeOptions(q.time_limit)),
      el("label", { class: "button" }, picture ? "Change picture" : "Add picture", pictureInput),
      picture ? el("button", { onclick: () => setSlideImage(q.id, null) }, "Remove picture") : null,
    ),
  );
}

async function refresh({ updateSlides = true } = {}) {
  try {
    const [loaded, state] = await Promise.all([
      loadSlides(code, hostKey),
      request("GET", `${sessionPath(code)}/state`),
    ]);
    slides = byPosition(loaded.list);
    activeQuestion = state.active_question;
    activeId = loaded.active ?? activeQuestion?.id ?? null;
    if (updateSlides) $("questions").replaceChildren(...(slides.length ? slides.map(slideItem) : [el("li", { class: "muted" }, "No slides yet. Add one below.")]));
    renderLiveDashboard({
      question: activeQuestion,
      slides,
      code,
      onPrev: () => activateSlide(slides[slides.findIndex((slide) => slide.id === activeId) - 1]?.id),
      onNext: () => activateSlide(slides[slides.findIndex((slide) => slide.id === activeId) + 1]?.id),
      onToggleVoting: () => activeQuestion && patchSlide(activeQuestion.id, { is_open: !activeQuestion.is_open }),
      onToggleResults: () => activeQuestion && patchSlide(activeQuestion.id, { results_visible: !activeQuestion.results_visible }),
      onTimerDone: () => refresh({ updateSlides: false }),
    });
    if (dashboard.currentTab() === "results") refreshResults();
  } catch (err) {
    $("questions").replaceChildren(el("li", { class: "error" }, err.status === 401 ? "Host key not accepted." : "Can't reach the server. Try again in a moment."));
    $("live-preview").replaceChildren(el("p", { class: "error" }, "Can't reach the server. Try again in a moment."));
  }
}

async function refreshResults() {
  if (!slides.length) return renderResultsDashboard($("results-list"), slides, []);
  try {
    const data = await request("GET", `${sessionPath(code)}/results`, { hostKey });
    renderResultsDashboard($("results-list"), slides, data.results || []);
  } catch (err) {
    $("results-list").replaceChildren(el("p", { class: "card error" }, `Could not load results: ${err.message}`));
  }
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
