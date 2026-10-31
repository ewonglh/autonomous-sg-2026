// The slide list, shared by the host setup page and the presenter (which needs it to move between
// slides). Comes from GET /questions (issue #11). Until the server has it, the host page keeps a
// local copy of what it created, and the presenter uses that when opened on the same computer.
import { ApiError, request, sessionPath } from "./api.js";

const localKey = (code) => `crowdpulse-host-${code}`;

export function localSlides(code) {
  try {
    return JSON.parse(localStorage.getItem(localKey(code))) || [];
  } catch {
    return [];
  }
}

export function saveLocal(code, list) {
  try {
    localStorage.setItem(localKey(code), JSON.stringify(list));
  } catch {
    /* storage blocked */
  }
}

export function patchLocal(code, id, changes) {
  saveLocal(code, localSlides(code).map((q) => (q.id === id ? { ...q, ...changes } : q)));
}

export const notFound = (err) => err instanceof ApiError && [404, 405].includes(err.status);
export const byPosition = (list) => [...list].sort((a, b) => (a.position ?? 0) - (b.position ?? 0));

// Returns {list, active}: the slides in order and the id of the one on screen (or null).
export async function loadSlides(code, hostKey) {
  try {
    const data = await request("GET", `${sessionPath(code)}/questions`, { hostKey });
    return { list: byPosition(data.questions), active: data.active_question_id };
  } catch (err) {
    if (!notFound(err)) throw err;
    const state = await request("GET", `${sessionPath(code)}/state`);
    const a = state.active_question;
    const list = localSlides(code).map((q) => (a && q.id === a.id ? { ...q, is_open: a.is_open, results_visible: a.results_visible } : q));
    return { list: byPosition(list), active: a ? a.id : null };
  }
}

// Puts a slide on screen. The server opens it for voting and closes the one it replaces (issue #5).
export function showSlide(code, hostKey, id) {
  return request("POST", `${sessionPath(code)}/active`, { body: { question_id: id }, hostKey });
}
