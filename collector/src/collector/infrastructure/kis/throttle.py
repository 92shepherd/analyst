"""KIS 레이트리밋 스로틀 (토큰버킷 기반, async 안전).

KIS 호출 한도를 어댑터/클라이언트 경계에서 관리한다.
"""
from __future__ import annotations

import asyncio
import time


class RateLimiter:
    """초당 N개 요청으로 제한하는 토큰버킷."""

    def __init__(self, rate_per_sec: float, burst: int | None = None) -> None:
        if rate_per_sec <= 0:
            raise ValueError("rate_per_sec는 0보다 커야 합니다.")
        self._rate = rate_per_sec
        self._capacity = burst if burst is not None else max(1, int(rate_per_sec))
        self._tokens = float(self._capacity)
        self._updated = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            while True:
                now = time.monotonic()
                elapsed = now - self._updated
                self._updated = now
                self._tokens = min(
                    self._capacity, self._tokens + elapsed * self._rate
                )
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return
                wait = (1.0 - self._tokens) / self._rate
                await asyncio.sleep(wait)
