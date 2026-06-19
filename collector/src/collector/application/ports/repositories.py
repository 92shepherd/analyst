"""아웃바운드 포트: 영속성(DB) 접근.

- StockRepositoryPort: 종목 마스터(수집 대상 유니버스)를 읽는다. (마스터는 DB에 적재되어 있다고 가정)
- PriceRepositoryPort: 수집한 일봉을 적재한다.
"""
from __future__ import annotations

from datetime import date
from typing import Protocol, runtime_checkable

from collector.domain import DailyPrice, Market, Stock


@runtime_checkable
class StockRepositoryPort(Protocol):
    async def list_active_stocks(
        self, markets: list[Market] | None = None
    ) -> list[Stock]:
        """수집 대상(활성) 종목 목록을 반환한다.

        Args:
            markets: 특정 시장만 필터링. None이면 전 시장.
        """
        ...


@runtime_checkable
class PriceRepositoryPort(Protocol):
    async def save_daily_prices(self, prices: list[DailyPrice]) -> int:
        """일봉을 upsert 한다. 반환값은 처리한 행 수.

        (ticker, market, trade_date) 유니크 키 기준 멱등 적재.
        """
        ...

    async def latest_trade_date(self, stock: Stock) -> date | None:
        """해당 종목의 가장 최근 적재 거래일. 없으면 None.

        증분 수집 시 시작일 계산에 사용한다.
        """
        ...
