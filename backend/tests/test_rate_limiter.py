"""Tests for the sliding-window rate limiter."""

import time

import pytest

from rate_limiter import SlidingWindowLimiter


def test_allows_within_quota():
    lim = SlidingWindowLimiter()
    for _ in range(10):
        allowed, _ = lim.allow("t1", max_requests=10, window_seconds=60)
        assert allowed


def test_rejects_over_quota():
    lim = SlidingWindowLimiter()
    for _ in range(5):
        lim.allow("t2", max_requests=5, window_seconds=60)
    allowed, retry = lim.allow("t2", max_requests=5, window_seconds=60)
    assert not allowed
    assert retry > 0


def test_window_expiry():
    """Requests should be allowed again after the window elapses."""
    lim = SlidingWindowLimiter()
    # Fill the window with a very short window
    for _ in range(3):
        lim.allow("t3", max_requests=3, window_seconds=0.1)
    allowed, _ = lim.allow("t3", max_requests=3, window_seconds=0.1)
    assert not allowed

    time.sleep(0.15)
    allowed, _ = lim.allow("t3", max_requests=3, window_seconds=0.1)
    assert allowed


def test_separate_tenants():
    lim = SlidingWindowLimiter()
    for _ in range(5):
        lim.allow("t4", max_requests=5, window_seconds=60)
    # t4 is full
    allowed_t4, _ = lim.allow("t4", max_requests=5, window_seconds=60)
    assert not allowed_t4
    # t5 should be fine
    allowed_t5, _ = lim.allow("t5", max_requests=5, window_seconds=60)
    assert allowed_t5


def test_current_count():
    lim = SlidingWindowLimiter()
    for _ in range(7):
        lim.allow("t6", max_requests=100, window_seconds=60)
    assert lim.current_count("t6", 60) == 7


def test_concurrency_acquire_release():
    lim = SlidingWindowLimiter()
    assert lim.acquire_concurrency("t7", max_concurrency=2)
    assert lim.acquire_concurrency("t7", max_concurrency=2)
    assert not lim.acquire_concurrency("t7", max_concurrency=2)
    lim.release_concurrency("t7")
    assert lim.acquire_concurrency("t7", max_concurrency=2)


def test_reset_tenant():
    lim = SlidingWindowLimiter()
    for _ in range(5):
        lim.allow("t8", max_requests=5, window_seconds=60)
    lim.reset("t8")
    assert lim.current_count("t8", 60) == 0


def test_reset_all():
    lim = SlidingWindowLimiter()
    lim.allow("t9", max_requests=10, window_seconds=60)
    lim.allow("t10", max_requests=10, window_seconds=60)
    lim.reset()
    assert lim.current_count("t9", 60) == 0
    assert lim.current_count("t10", 60) == 0
