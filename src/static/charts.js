// Bar chart, donut chart and word cloud. Plain DOM and SVG, no libraries.
import { el } from "./api.js";

const COLORS = ["--c1", "--c2", "--c3", "--c4", "--c5", "--c6"].map((v) => `var(${v})`);
const color = (i) => COLORS[i % COLORS.length];
const pct = (n, total) => (total ? Math.round((n / total) * 100) : 0);

// options: [{label, count}]
export function renderBars(options) {
  const total = options.reduce((sum, o) => sum + o.count, 0);
  const max = Math.max(1, ...options.map((o) => o.count));
  return el(
    "div",
    { class: "bars", role: "list" },
    options.map((o, i) =>
      el(
        "div",
        { role: "listitem" },
        el("div", { class: "bar-label" }, el("span", {}, o.label), el("span", { class: "muted" }, `${o.count} · ${pct(o.count, total)}%`)),
        el("div", { class: "bar-track" }, el("div", { class: "bar-fill", style: `width:${(o.count / max) * 100}%;background:${color(i)}` })),
      ),
    ),
  );
}

export function renderDonut(options) {
  const total = options.reduce((sum, o) => sum + o.count, 0);
  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  svg.setAttribute("viewBox", "0 0 42 42");
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", options.map((o) => `${o.label}: ${o.count}`).join(", "));
  const ring = (stroke, dash, offset) => {
    const c = document.createElementNS(ns, "circle");
    Object.entries({ cx: 21, cy: 21, r: 15.915, fill: "none", "stroke-width": 6 }).forEach(([k, v]) => c.setAttribute(k, v));
    c.setAttribute("stroke", stroke);
    if (dash) c.setAttribute("stroke-dasharray", dash);
    c.setAttribute("stroke-dashoffset", offset);
    return c;
  };
  svg.append(ring("var(--bg)", null, 0));
  let used = 0;
  options.forEach((o, i) => {
    const share = total ? (o.count / total) * 100 : 0;
    if (share > 0) svg.append(ring(color(i), `${share} ${100 - share}`, 25 - used));
    used += share;
  });
  const label = document.createElementNS(ns, "text");
  Object.entries({ x: 21, y: 23.5, "text-anchor": "middle", "font-size": 7, fill: "currentColor", "font-weight": 700 }).forEach(([k, v]) => label.setAttribute(k, v));
  label.textContent = String(total);
  svg.append(label);
  const legend = el(
    "ul",
    { class: "legend" },
    options.map((o, i) => el("li", {}, el("span", { class: "swatch", style: `background:${color(i)}` }), `${o.label} — ${o.count} (${pct(o.count, total)}%)`)),
  );
  return el("div", { class: "donut" }, svg, legend);
}

// words: [{word, count}]
export function renderWordCloud(words) {
  if (!words.length) return el("p", { class: "muted" }, "No words yet.");
  const sorted = [...words].sort((a, b) => b.count - a.count).slice(0, 60);
  const max = sorted[0].count;
  const min = sorted[sorted.length - 1].count;
  return el(
    "div",
    { class: "cloud", "aria-label": "Word cloud" },
    sorted.map((w, i) => {
      const weight = max === min ? 1 : (w.count - min) / (max - min);
      const size = 1 + weight * 2.6;
      return el("span", { title: `${w.count}`, style: `font-size:${size}em;color:${color(i)}` }, w.word);
    }),
  );
}

// Picks the right chart for one question's results. kind is "bar" or "donut" for multiple choice.
export function renderResults(result, kind = "bar") {
  if (!result) return el("p", { class: "muted" }, "No results yet.");
  if (result.words) return renderWordCloud(result.words);
  const options = result.options || [];
  return kind === "donut" ? renderDonut(options) : renderBars(options);
}
