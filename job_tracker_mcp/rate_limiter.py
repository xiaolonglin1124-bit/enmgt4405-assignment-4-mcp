"""A small, thread-safe sliding-window rate limiter."""

from collections import defaultdict, deque
from collections.abc import Callable
from threading import Lock
import time

from .errors import RateLimitExceeded


class SlidingWindowRateLimiter:
    def __init__(
        self,
        max_calls: int,
        window_seconds: int,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if max_calls < 1 or window_seconds < 1:
            raise ValueError("Rate-limit values must be positive")
        self.max_calls = max_calls
        self.window_seconds = window_seconds
        self._clock = clock
        self._calls: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def check(self, key: str) -> None:
        now = self._clock()
        cutoff = now - self.window_seconds

        with self._lock:
            timestamps = self._calls[key]
            while timestamps and timestamps[0] <= cutoff:
                timestamps.popleft()

            if len(timestamps) >= self.max_calls:
                retry_after = int(timestamps[0] + self.window_seconds - now) + 1
                raise RateLimitExceeded(retry_after)

            timestamps.append(now)
