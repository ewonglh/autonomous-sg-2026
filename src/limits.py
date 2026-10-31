"""Small in-memory sliding-window request limits."""
from collections import deque
from collections.abc import Callable, Hashable
from math import ceil
from threading import Lock
from time import monotonic


WINDOW_SECONDS = 60


class RateLimiter:
    """Track accepted requests per key for one rolling time window."""

    def __init__(
        self,
        clock: Callable[[], float] = monotonic,
        window_seconds: int = WINDOW_SECONDS,
    ) -> None:
        self._clock = clock
        self._window_seconds = window_seconds
        self._requests: dict[Hashable, deque[float]] = {}
        self._lock = Lock()

    def check_request(self, key: Hashable, limit: int) -> int | None:
        """Record an allowed request, or return its retry delay in seconds."""
        with self._lock:
            now = self._clock()
            cutoff = now - self._window_seconds
            requests = self._requests.get(key)
            if requests is None:
                requests = deque()
                self._requests[key] = requests

            while requests and requests[0] <= cutoff:
                requests.popleft()

            if len(requests) >= limit:
                remaining = self._window_seconds - (now - requests[0])
                return max(1, ceil(remaining))

            requests.append(now)
            return None
