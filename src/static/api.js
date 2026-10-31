// Shared helpers for talking to the CrowdPulse API. See docs/API.md.

export class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
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

export function participantId() {
  const name = "crowdpulse-participant-id";
  try {
    let id = localStorage.getItem(name);
    if (!id) {
      id = crypto.randomUUID();
      localStorage.setItem(name, id);
    }
    return id;
  } catch {
    return (window.__cpId ||= crypto.randomUUID());
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
    try {
      detail = (await res.json()).detail || detail;
    } catch {
      /* not JSON */
    }
    // FastAPI validation errors (422) come as a list of {loc, msg}; show the first message.
    if (Array.isArray(detail)) detail = detail.map((d) => d.msg).filter(Boolean)[0];
    throw new ApiError(res.status, typeof detail === "string" && detail ? detail : `Request failed (${res.status})`);
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
