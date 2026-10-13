"""
CloudShield FairGuard — In-memory sliding-window rate limiter.

IMPORTANT: This limiter coordinates a **single backend process** only.
It stores timestamps in memory and does NOT persist across restarts.
For a multi-process deployment, replace with a Redis-backed implementation.

Algorithm
---------
For each tenant, we maintain a deque of request timestamps. On each
incoming request we:
1. Evict timestamps older than ``window_seconds``.
2. Check whether ``len(timestamps) >= requests_per_minute``.
3. If over quota, reject; otherwise, record the timestamp and accept.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from threading import Lock


@dataclass
class TenantWindow:
    """Per-tenant sliding window state."""
    timestamps: deque[float] = field(default_factory=deque)
    lock: Lock = field(default_factory=Lock)


class SlidingWindowLimiter:
    """Single-process, in-memory sliding-window rate limiter.

    NOT safe for multi-process deployments.  See module docstring.
    """

    def __init__(self) -> None:
        self._windows: dict[str, TenantWindow] = defaultdict(TenantWindow)
        # Active concurrency counters
        self._concurrency: dict[str, int] = defaultdict(int)
        self._concurrency_lock = Lock()

    # ----- rate limiting -----

    def allow(
        self,
        tenant_id: str,
        max_requests: int,
        window_seconds: int = 60,
    ) -> tuple[bool, float]:
        """Check whether a request from *tenant_id* should be allowed.

        Returns ``(allowed, retry_after_seconds)``.
        ``retry_after_seconds`` is 0 when allowed, otherwise an estimate.
        """
        tw = self._windows[tenant_id]
        now = time.monotonic()
        cutoff = now - window_seconds

        with tw.lock:
            # Evict expired timestamps
            while tw.timestamps and tw.timestamps[0] < cutoff:
                tw.timestamps.popleft()

            if len(tw.timestamps) >= max_requests:
                # Over quota — estimate when the oldest entry will expire
                oldest = tw.timestamps[0] if tw.timestamps else now
                retry_after = max(0.0, (oldest + window_seconds) - now)
                return False, retry_after

            tw.timestamps.append(now)
            return True, 0.0

    def current_count(self, tenant_id: str, window_seconds: int = 60) -> int:
        """Return the number of requests in the current window."""
        tw = self._windows[tenant_id]
        now = time.monotonic()
        cutoff = now - window_seconds
        with tw.lock:
            while tw.timestamps and tw.timestamps[0] < cutoff:
                tw.timestamps.popleft()
            return len(tw.timestamps)

    # ----- concurrency tracking -----

    def acquire_concurrency(self, tenant_id: str, max_concurrency: int) -> bool:
        """Try to acquire a concurrency slot.  Returns True on success."""
        with self._concurrency_lock:
            current = self._concurrency[tenant_id]
            if current >= max_concurrency:
                return False
            self._concurrency[tenant_id] = current + 1
            return True

    def release_concurrency(self, tenant_id: str) -> None:
        """Release a concurrency slot."""
        with self._concurrency_lock:
            self._concurrency[tenant_id] = max(0, self._concurrency[tenant_id] - 1)

    def current_concurrency(self, tenant_id: str) -> int:
        with self._concurrency_lock:
            return self._concurrency[tenant_id]

    def reset(self, tenant_id: str | None = None) -> None:
        """Reset state.  If *tenant_id* is None, reset everything."""
        if tenant_id:
            self._windows.pop(tenant_id, None)
            with self._concurrency_lock:
                self._concurrency.pop(tenant_id, None)
        else:
            self._windows.clear()
            with self._concurrency_lock:
                self._concurrency.clear()


# Global singleton — shared by all routes in the single-process server.
limiter = SlidingWindowLimiter()
