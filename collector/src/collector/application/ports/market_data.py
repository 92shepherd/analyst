"""아웃바운드 포트: 외부 시세 데이터 조회.

어댑터(KIS REST)가 이 포트를 구현한다. 유즈케이스는 이 인터페이스에만 의존하며
KIS/httpx 등 구체 기술을 알지 못한다.

단일 호출로 일봉(가격)과 밸류에이션 스냅샷을 함께 반환한다(국내 일봉 응답의 output1 재사용).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Protocol, runtime_checkable

from collector.domain import DailyPrice, Stock, ValuationSnapshot


@dataclass(frozen=True)
class DailyMarketData:
    """일봉 시세 + (가능하면) 밸류에이션 스냅샷.

    valuation은 best-effort다. 국내는 일봉 응답 output1에서 추출하고,
    해외(KIS 미제공)나 파싱 불가 시 None일 수 있다.
    """

    prices: list[DailyPrice] = field(default_factory=list)
    valuation: ValuationSnapshot | None = None


@runtime_checkable
class MarketDataPort(Protocol):
    """종목의 기간별 일봉 시세(+밸류에이션)를 조회하는 포트."""

    async def fetch_daily(
        self, stock: Stock, start: date, end: date
    ) -> DailyMarketData:
        """[start, end] 구간의 일봉(거래일 오름차순)과 밸류에이션 스냅샷을 반환한다.

        Raises:
            MarketDataUnavailableError: 외부 시세 조회 실패 시(가격이 핵심이므로 예외).
        """
        ...
