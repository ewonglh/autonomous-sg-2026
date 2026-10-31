// Shared helpers for talking to the CrowdPulse API. See docs/API.md.

export class ApiError extends Error {
  constructor(status, message, code) {
    super(message);
    this.status = status;
    this.code = code; // short reason from the server when it sends one (issue #36)
  }
}

// Why the server turned an answer down: "already_responded", "closed", "rate_limited",
// "limit_reached" or "other".
// Uses the server's `code` when there is one, otherwise reads the message (the server uses status
// 409 for several different reasons today, so the status alone is not enough).
export function rejection(err) {
  const text = err.message || "";
  if (["already_responded", "closed", "rate_limited", "limit_reached"].includes(err.code)) return err.code;
  if (err.status === 429 || /rate limit/i.test(text)) return "rate_limited";
  if (err.status === 409 && /already/i.test(text)) return "already_responded";
  if (/closed/i.test(text)) return "closed";
  if (/limit/i.test(text)) return "limit_reached";
  return "other";
}

// The session code is the last part of the page path, e.g. /host/ABC123.
export function codeFromPath() {
  const parts = location.pathname.split("/").filter(Boolean);
  return parts.length > 1 ? decodeURIComponent(parts[1]) : null;
}

// The host key lives only in the URL fragment (#key=...), so it never reaches the server logs.
export function hostKeyFromHash() {
  return new URLSearchParams(location.hash.slice(1)).get("key");
}

// crypto.randomUUID only exists on https pages and localhost, so a phone opening the plain-http
// address of this computer on the same Wi-Fi would crash. getRandomValues works everywhere.
function newId() {
  if (crypto.randomUUID) return crypto.randomUUID();
  const b = crypto.getRandomValues(new Uint8Array(16));
  b[6] = (b[6] & 0x0f) | 0x40;
  b[8] = (b[8] & 0x3f) | 0x80;
  const h = Array.from(b, (x) => x.toString(16).padStart(2, "0")).join("");
  return `${h.slice(0, 8)}-${h.slice(8, 12)}-${h.slice(12, 16)}-${h.slice(16, 20)}-${h.slice(20)}`;
}

export function participantId() {
  const name = "crowdpulse-participant-id";
  try {
    let id = localStorage.getItem(name);
    if (!id) {
      id = newId();
      localStorage.setItem(name, id);
    }
    return id;
  } catch {
    return (window.__cpId ||= newId());
  }
}

export async function request(method, path, { body, hostKey, participant } = {}) {
  const headers = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (hostKey) headers.Authorization = `Bearer ${hostKey}`;
  if (participant) headers["X-Participant-Id"] = participantId();
  const res = await fetch(path, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!res.ok) {
    let detail = res.statusText;
    let code;
    try {
      const body = await res.json();
      detail = body.detail || detail;
      code = body.code;
    } catch {
      /* not JSON */
    }
    // FastAPI validation errors (422) come as a list of {loc, msg}; show the first message.
    if (Array.isArray(detail)) detail = detail.map((d) => d.msg).filter(Boolean)[0];
    throw new ApiError(res.status, typeof detail === "string" && detail ? detail : `Request failed (${res.status})`, code);
  }
  const type = res.headers.get("Content-Type") || "";
  return type.includes("application/json") ? res.json() : res.blob();
}

export const sessionPath = (code) => `/api/sessions/${encodeURIComponent(code)}`;

// How a poll's results are drawn. Set by the host per question; older servers have no `chart`.
export const chartOf = (question) => (question && question.chart === "donut" ? "donut" : "bar");

// Calls onChange whenever the server says something changed. Uses the WebSocket when it
// works and also polls every few seconds, so the screens keep updating if the socket drops.
// Returns a stop() function that ends the updates.
export function subscribe(code, onChange, pollMs = 3000) {
  let socket;
  let retry = 1000;
  let stopped = false;
  const connect = () => {
    if (stopped) return;
    const proto = location.protocol === "https:" ? "wss" : "ws";
    socket = new WebSocket(`${proto}://${location.host}/ws/${encodeURIComponent(code)}`);
    socket.onmessage = (event) => {
      if (stopped) return;
      let msg = {};
      try {
        msg = JSON.parse(event.data);
      } catch {
        /* ignore bad message */
      }
      onChange(msg.type || "changed");
    };
    socket.onopen = () => (retry = 1000);
    socket.onclose = () => {
      setTimeout(connect, retry);
      retry = Math.min(retry * 2, 15000);
    };
  };
  connect();
  const timer = setInterval(() => !stopped && onChange("poll"), pollMs);
  onChange("start");
  return () => {
    stopped = true;
    clearInterval(timer);
    try {
      socket.close();
    } catch {
      /* already closed */
    }
  };
}

// Small DOM helper: el("p", {class: "muted"}, "text", child). Text is always set as text, never HTML.
export function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === undefined || v === null || v === false) continue;
    if (k.startsWith("on")) node.addEventListener(k.slice(2), v);
    else if (k === "class") node.className = v;
    else node.setAttribute(k, v === true ? "" : v);
  }
  for (const child of children.flat()) {
    if (child === null || child === undefined || child === false) continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}
