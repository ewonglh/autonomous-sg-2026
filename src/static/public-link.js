import { request } from "./api.js";

export function watchPublicLink(code, input) {
  let origin = null;
  let enabled = false;
  const update = async () => {
    try {
      ({ origin, enabled } = await request("GET", "/public-origin"));
      input.value = code && origin ? `${origin}/join/${encodeURIComponent(code)}` :
        code && enabled ? "Finding the public link…" : code ? `${location.origin}/join/${encodeURIComponent(code)}` : "";
    } catch {
      /* the local app remains usable while the tunnel starts */
    }
  };
  update();
  setInterval(update, 2000);
  return {
    get origin() { return origin; },
    get enabled() { return enabled; },
    async wait(timeout) {
      const deadline = Date.now() + timeout;
      while (!origin && Date.now() < deadline) {
        await update();
        if (!origin) await new Promise((resolve) => setTimeout(resolve, 500));
      }
      return origin;
    },
  };
}
