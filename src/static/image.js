// Optional picture for each slide. It shows to the right of the question on the presenter screen
// and changes with the slide. The host shrinks it in the browser and sends it to the server
// (issue #30). Until the server supports that, a copy is kept in this browser's storage, which
// reaches a presenter tab opened from the host screen on the same computer.
import { ApiError, request, sessionPath } from "./api.js";

const MAX_SIDE = 800;
const keyFor = (code, qid) => `crowdpulse-image-${code}-${qid}`;

// Reads an image file and returns a shrunk PNG data URL (keeps transparency for logos).
export function shrinkImage(file) {
  return new Promise((resolve, reject) => {
    if (!file || !file.type.startsWith("image/")) return reject(new Error("Choose an image file (PNG, JPG, SVG or GIF)."));
    const url = URL.createObjectURL(file);
    const img = new Image();
    img.onload = () => {
      const scale = Math.min(1, MAX_SIDE / Math.max(img.naturalWidth || MAX_SIDE, img.naturalHeight || MAX_SIDE));
      const canvas = document.createElement("canvas");
      canvas.width = Math.max(1, Math.round((img.naturalWidth || MAX_SIDE) * scale));
      canvas.height = Math.max(1, Math.round((img.naturalHeight || MAX_SIDE) * scale));
      canvas.getContext("2d").drawImage(img, 0, 0, canvas.width, canvas.height);
      URL.revokeObjectURL(url);
      resolve(canvas.toDataURL("image/png"));
    };
    img.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error("That image could not be opened. Try a PNG or JPG."));
    };
    img.src = url;
  });
}

export function loadImage(code, qid) {
  try {
    return localStorage.getItem(keyFor(code, qid));
  } catch {
    return null;
  }
}

// Returns false if the browser would not store it (storage blocked or full).
export function saveImage(code, qid, dataUrl) {
  try {
    if (dataUrl) localStorage.setItem(keyFor(code, qid), dataUrl);
    else localStorage.removeItem(keyFor(code, qid));
    return true;
  } catch {
    return false;
  }
}

// The slide's picture: the server's copy if it has one, otherwise this browser's copy.
export const imageOf = (code, question) => (question ? question.image_url || loadImage(code, question.id) : null);

// Sends the picture (or removes it) on the server. Servers without image support are fine:
// the local copy still works.
export async function uploadImage(code, qid, hostKey, dataUrl) {
  const path = `${sessionPath(code)}/questions/${qid}/image`;
  try {
    if (dataUrl) await request("PUT", path, { body: { data_url: dataUrl }, hostKey });
    else await request("DELETE", path, { hostKey });
  } catch (err) {
    if (!(err instanceof ApiError) || ![404, 405].includes(err.status)) throw err;
  }
}

// Calls onChange() when another tab adds or removes a slide's picture.
export function watchImage(code, onChange) {
  window.addEventListener("storage", (event) => {
    if (event.key && event.key.startsWith(`crowdpulse-image-${code}-`)) onChange();
  });
}

// Shows dataUrl in an <img>, or hides it when there is none.
export function showImage(img, dataUrl) {
  img.hidden = !dataUrl;
  if (dataUrl) img.src = dataUrl;
  else img.removeAttribute("src");
}
