"""아웃바운드 포트: 외부 시세 데이터 조회.

어댑터(KIS REST)가 이 포트를 구현한다. 유즈케이스는 이 인터페이스에만 의존하며
KIS/httpx 등 구체 기술을 알지 못한다.
"""
from __future__ import annotations

from datetime import date
from typing import Protocol, runtime_checkable

from collector.domain import DailyPrice, Stock


@runtime_checkable
class MarketDataPort(Protocol):
    """종목의 기간별 일봉 시세를 조회하는 포트."""

    async def fetch_daily_prices(
        self, stock: Stock, start: date, end: date
    ) -> list[DailyPrice]:
        """[start, end] 구간의 일봉 목록을 거래일 오름차순으로 반환한다.

        Raises:
            MarketDataUnavailableError: 외부 조회 실패 시.
        """
        ...
