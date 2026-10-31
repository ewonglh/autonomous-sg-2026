// Countdown for timed slides. The server sends `seconds_left` on the active question (issue #26);
// each page re-syncs it on every refresh and ticks locally in between.

export const TIME_LIMITS = [0, 15, 30, 45, 60, 90, 120, 180, 300];

export function formatSeconds(total) {
  const s = Math.max(0, Math.ceil(total));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

export const limitLabel = (seconds) => (seconds ? (seconds < 60 ? `${seconds} sec` : `${seconds / 60} min`) : "No time limit");

export const secondsLeftOf = (q) => (q && typeof q.seconds_left === "number" && q.is_open ? q.seconds_left : null);

// Shows a ticking m:ss in `node`, hides it when there is no timer, and calls onDone once at zero.
export class Countdown {
  constructor(node, onDone) {
    this.node = node;
    this.onDone = onDone;
    this.deadline = null;
    this.fired = false;
    setInterval(() => this.tick(), 250);
  }

  set(secondsLeft) {
    if (secondsLeft === null) {
      this.deadline = null;
    } else {
      const deadline = Date.now() + secondsLeft * 1000;
      // Ignore tiny jitter between polls so the display does not jump back and forth.
      if (this.deadline === null || Math.abs(deadline - this.deadline) > 1500) this.deadline = deadline;
      if (secondsLeft > 0) this.fired = false;
    }
    this.tick();
  }

  tick() {
    if (this.deadline === null) {
      this.node.hidden = true;
      return;
    }
    const left = (this.deadline - Date.now()) / 1000;
    this.node.hidden = false;
    this.node.textContent = left > 0 ? formatSeconds(left) : "Time's up";
    this.node.classList.toggle("ending", left > 0 && left <= 5);
    if (left <= 0 && !this.fired) {
      this.fired = true;
      // Give the server a moment to close voting, then refresh.
      setTimeout(() => this.onDone(), 600);
    }
  }
}
