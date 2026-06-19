"""테스트용 인메모리 가짜 포트 (단일 모델: ticker는 str)."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from collector.domain import DailyPrice, Market, MarketDataUnavailableError, Stock


class FakeStockRepository:
    def __init__(self, stocks: list[Stock]) -> None:
        self._stocks = stocks

    async def list_active_stocks(self, markets=None) -> list[Stock]:
        if markets is None:
            return list(self._stocks)
        return [s for s in self._stocks if s.market in markets]


class FakeMarketData:
    """종목별로 미리 정해둔 일봉을 반환. 'FAIL' 티커는 예외."""

    def __init__(self, data: dict[str, list[DailyPrice]]) -> None:
        self._data = data
        self.calls: list[tuple[str, date, date]] = []

    async def fetch_daily_prices(
        self, stock: Stock, start: date, end: date
    ) -> list[DailyPrice]:
        self.calls.append((stock.ticker, start, end))
        if stock.ticker == "FAIL":
            raise MarketDataUnavailableError("의도된 실패")
        rows = self._data.get(stock.ticker, [])
        return [p for p in rows if start <= p.trade_date <= end]


class FakePriceRepository:
    def __init__(self, latest: dict[str, date] | None = None) -> None:
        self.saved: list[DailyPrice] = []
        self._latest = latest or {}

    async def save_daily_prices(self, prices: list[DailyPrice]) -> int:
        self.saved.extend(prices)
        return len(prices)

    async def latest_trade_date(self, stock: Stock) -> date | None:
        return self._latest.get(stock.ticker)


def make_price(ticker: str, market: Market, d: date, close: str = "100") -> DailyPrice:
    return DailyPrice(
        ticker=ticker,
        market=market,
        trade_date=d,
        open=Decimal(close),
        high=Decimal(close),
        low=Decimal(close),
        close=Decimal(close),
        volume=1000,
    )


@pytest.fixture
def samsung() -> Stock:
    return Stock(ticker="005930", market=Market.KOSPI, name="삼성전자")


@pytest.fixture
def apple() -> Stock:
    return Stock(ticker="AAPL", market=Market.NASDAQ, name="Apple")
