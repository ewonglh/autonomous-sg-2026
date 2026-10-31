// Compact dashboard tabs and the live host preview.
import { chartOf, el } from "./api.js";
import { renderResults } from "./charts.js";
import { imageOf, showImage } from "./image.js";
import { Countdown, secondsLeftOf } from "./timer.js";

const $ = (id) => document.getElementById(id);
let selectedTab = "live";
let countdown;

export function setupHostDashboard(onTabChange) {
  const names = ["live", "slides", "results"];
  const select = (name) => {
    selectedTab = name;
    names.forEach((item) => {
      const tab = $(`tab-${item}`);
      tab.setAttribute("aria-selected", String(item === name));
      tab.tabIndex = item === name ? 0 : -1;
      $(`panel-${item}`).hidden = item !== name;
    });
    onTabChange(name);
  };
  names.forEach((name) => {
    $(`tab-${name}`).addEventListener("click", () => select(name));
    $(`tab-${name}`).addEventListener("keydown", (event) => {
      const index = names.indexOf(name);
      const next = event.key === "ArrowRight" ? (index + 1) % names.length : event.key === "ArrowLeft" ? (index + names.length - 1) % names.length : -1;
      if (next < 0) return;
      event.preventDefault();
      $(`tab-${names[next]}`).focus();
      select(names[next]);
    });
  });
  return { currentTab: () => selectedTab };
}

function badge(text, kind = "") {
  return el("span", { class: `badge ${kind}`.trim() }, text);
}

function renderPreview(question, code) {
  if (!question) return el("p", { class: "muted" }, "No slide on screen.");
  const content = [el("h2", { class: "preview-question" }, question.text)];
  const image = imageOf(code, question);
  if (image) {
    const img = el("img", { class: "preview-image", alt: "Slide image" });
    showImage(img, image);
    content.push(img);
  }
  if (question.type === "multiple_choice" && !question.results_visible) {
    content.push(el("ul", { class: "preview-options" }, (question.options || []).map((option) => el("li", {}, option.label))));
  } else if (question.type === "qa") {
    content.push(el("p", { class: "muted" }, question.is_open ? "Audience questions are open." : "Audience questions are closed."));
  } else if (question.results_visible) {
    content.push(renderResults(question.results, chartOf(question)));
  } else {
    content.push(el("p", { class: "muted" }, "Results are hidden."));
  }
  return el("div", { class: "preview-content" }, content);
}

export function renderLiveDashboard({ question, slides, code, onPrev, onNext, onToggleVoting, onToggleResults, onTimerDone }) {
  if (!countdown) countdown = new Countdown($("live-timer"), onTimerDone);
  const index = slides.findIndex((slide) => slide.id === question?.id);
  $("live-position").textContent = index < 0 ? "No active slide" : `Slide ${index + 1} of ${slides.length}`;
  $("previous-slide").disabled = index <= 0;
  $("next-slide").disabled = index < 0 || index >= slides.length - 1;
  $("toggle-voting").hidden = !question;
  $("toggle-results").hidden = !question || question.type === "qa";
  if (question) {
    $("toggle-voting").textContent = question.is_open ? (question.type === "qa" ? "Close questions" : "Close voting") : (question.type === "qa" ? "Open questions" : "Open voting");
    $("toggle-results").textContent = question.results_visible ? "Hide results" : "Reveal results";
  }
  $("previous-slide").onclick = onPrev;
  $("next-slide").onclick = onNext;
  $("toggle-voting").onclick = onToggleVoting;
  $("toggle-results").onclick = onToggleResults;

  const meta = $("live-meta");
  if (!question) {
    countdown.set(null);
    meta.replaceChildren(badge("Waiting for a slide"));
  } else {
    const items = [badge(question.is_open ? (question.type === "qa" ? "Questions open" : "Voting open") : (question.type === "qa" ? "Questions closed" : "Voting closed"), question.is_open ? "on" : "")];
    if (typeof question.response_count === "number") items.push(badge(`${question.response_count} ${question.type === "qa" ? "questions" : "responses"}`));
    const timer = $("live-timer");
    items.push(timer);
    countdown.set(secondsLeftOf(question));
    meta.replaceChildren(...items);
  }
  $("live-preview").replaceChildren(renderPreview(question, code));
}

export function renderResultsDashboard(root, slides, results) {
  if (!slides.length) {
    root.replaceChildren(el("p", { class: "card muted" }, "Add a slide to start collecting results."));
    return;
  }
  root.replaceChildren(...slides.map((slide, index) => {
    const result = results.find((item) => item.question_id === slide.id);
    const title = el("div", { class: "results-card-heading" },
      el("span", { class: "slide-num" }, String(index + 1)),
      el("h3", {}, slide.text),
      badge(slide.results_visible ? "Live" : "Hidden", slide.results_visible ? "on" : ""),
    );
    const chart = slide.type === "qa" ? el("p", { class: "muted" }, `${slide.response_count || 0} audience questions`) : renderResults(result, chartOf(slide));
    return el("article", { class: "card results-card" }, title, chart);
  }));
}
