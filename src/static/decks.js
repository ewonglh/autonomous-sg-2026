// Save reusable slide definitions as a small, versioned JSON file.
import { chartOf, request, sessionPath } from "./api.js";

const FORMAT = "crowdpulse-slide-deck";
const TYPES = new Set(["multiple_choice", "word_cloud", "qa"]);
const isObject = (value) => value && typeof value === "object" && !Array.isArray(value);

function definition(slide) {
  return {
    type: slide.type,
    text: slide.text,
    options: slide.type === "multiple_choice" ? slide.options.map((option) => option.label) : [],
    ...(slide.type === "multiple_choice" ? { chart: chartOf(slide) } : {}),
    time_limit: slide.time_limit ?? null,
  };
}

export function downloadDeck(slides) {
  const file = new Blob([JSON.stringify({ format: FORMAT, version: 1, slides: slides.map(definition) }, null, 2)], {
    type: "application/json",
  });
  const url = URL.createObjectURL(file);
  const link = document.createElement("a");
  link.href = url;
  link.download = "crowdpulse-slides.json";
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function deckStatus(text, isError = false) {
  const status = document.getElementById("deck-status");
  status.hidden = false;
  status.className = isError ? "error" : "muted";
  status.textContent = text;
}

function validateDeck(data) {
  if (!isObject(data) || data.format !== FORMAT || data.version !== 1 || !Array.isArray(data.slides) || !data.slides.length) {
    throw new Error("Choose a valid CrowdPulse slide file.");
  }
  return data.slides.map((slide) => {
    if (!isObject(slide) || !TYPES.has(slide.type) || typeof slide.text !== "string") {
      throw new Error("A slide has an invalid type or question.");
    }
    const text = slide.text.trim();
    if (!text || text.length > 300) throw new Error("Slide questions must be 1 to 300 characters.");
    if (slide.time_limit !== null && slide.time_limit !== undefined && (!Number.isInteger(slide.time_limit) || slide.time_limit < 5 || slide.time_limit > 3600)) {
      throw new Error("Slide time limits must be 5 to 3600 seconds.");
    }
    const options = slide.options ?? [];
    if (!Array.isArray(options)) throw new Error("Slide options must be a list.");
    if (slide.type === "multiple_choice") {
      const labels = options.map((option) => typeof option === "string" ? option.trim() : "");
      if (labels.length < 2 || labels.length > 10 || labels.some((label) => !label || label.length > 100)) {
        throw new Error("Polls need 2 to 10 options, each 1 to 100 characters.");
      }
      if (new Set(labels.map((label) => label.toLocaleLowerCase())).size !== labels.length) {
        throw new Error("Poll options must be unique.");
      }
      const chart = slide.chart ?? "bar";
      if (!new Set(["bar", "donut"]).has(chart)) throw new Error("A poll has an invalid chart style.");
      return { type: slide.type, text, options: labels, chart, time_limit: slide.time_limit ?? null };
    }
    if (options.length || (slide.chart !== null && slide.chart !== undefined)) {
      throw new Error("Only polls can have options or a chart style.");
    }
    return { type: slide.type, text, options: [], time_limit: slide.time_limit ?? null };
  });
}

export async function createSlidesFromFile(file, code, hostKey) {
  let data;
  try {
    data = JSON.parse(await file.text());
  } catch {
    throw new Error("This file is not valid JSON.");
  }
  const slides = validateDeck(data);
  const created = [];
  for (const slide of slides) {
    const body = { ...slide };
    if (body.type !== "multiple_choice") delete body.chart;
    const result = await request("POST", `${sessionPath(code)}/questions`, { body, hostKey });
    created.push({ ...slide, id: result.id });
  }
  return created;
}

export function setupDeckControls({ code, hostKey, getSlides, onLoaded }) {
  document.getElementById("save-deck").onclick = () => {
    if (!getSlides().length) return deckStatus("Add at least one slide before saving.", true);
    downloadDeck(getSlides());
    deckStatus("Slide file saved.");
  };
  document.getElementById("load-deck-file").addEventListener("change", async (event) => {
    const file = event.target.files[0];
    event.target.value = "";
    if (!file) return;
    try {
      const created = await createSlidesFromFile(file, code, hostKey);
      await onLoaded();
      deckStatus(`${created.length} slides loaded.`);
    } catch (err) {
      deckStatus(`Could not load slides: ${err.message}`, true);
    }
  });
}
