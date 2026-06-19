"""KIS HTTP 클라이언트 (infrastructure).

- 접근 토큰 발급/만료/갱신을 이 계층에 캡슐화한다(호출부 비노출).
- 레이트리밋 스로틀을 적용한다.
- get_json은 KisApiClient 프로토콜을 만족한다(어댑터가 사용).
"""
from __future__ import annotations

import asyncio
import logging
import time

import httpx

from collector.infrastructure.config import Settings
from collector.infrastructure.kis.throttle import RateLimiter

logger = logging.getLogger(__name__)

_TOKEN_PATH = "/oauth2/tokenP"
# 만료 직전 갱신을 위한 여유(초).
_TOKEN_REFRESH_MARGIN = 60.0


class KisClient:
    """KIS Open API 저수준 클라이언트."""

    def __init__(self, settings: Settings, client: httpx.AsyncClient) -> None:
        self._settings = settings
        self._client = client
        self._limiter = RateLimiter(settings.kis_rate_limit_per_sec)
        self._token: str | None = None
        self._token_expiry: float = 0.0
        self._token_lock = asyncio.Lock()

    # ── 토큰 관리 ──────────────────────────────────────────────
    async def _ensure_token(self) -> str:
        now = time.monotonic()
        if self._token and now < self._token_expiry - _TOKEN_REFRESH_MARGIN:
            return self._token

        async with self._token_lock:
            now = time.monotonic()
            if self._token and now < self._token_expiry - _TOKEN_REFRESH_MARGIN:
                return self._token

            payload = {
                "grant_type": "client_credentials",
                "appkey": self._settings.kis_app_key,
                "appsecret": self._settings.kis_app_secret,
            }
            resp = await self._client.post(_TOKEN_PATH, json=payload)
            resp.raise_for_status()
            data = resp.json()
            self._token = data["access_token"]
            expires_in = float(data.get("expires_in", 86400))
            self._token_expiry = time.monotonic() + expires_in
            logger.info("KIS 토큰 발급 완료 (만료 %.0fs)", expires_in)
            return self._token

    # ── 요청 ──────────────────────────────────────────────────
    def _headers(self, tr_id: str, token: str) -> dict[str, str]:
        return {
            "content-type": "application/json; charset=utf-8",
            "authorization": f"Bearer {token}",
            "appkey": self._settings.kis_app_key,
            "appsecret": self._settings.kis_app_secret,
            "tr_id": tr_id,
            "custtype": "P",  # 개인
        }

    async def get_json(
        self, path: str, *, tr_id: str, params: dict[str, str]
    ) -> dict:
        token = await self._ensure_token()
        await self._limiter.acquire()
        resp = await self._client.get(
            path, params=params, headers=self._headers(tr_id, token)
        )
        resp.raise_for_status()
        return resp.json()


def create_http_client(settings: Settings) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=settings.kis_base_url,
        timeout=settings.kis_timeout_sec,
    )
