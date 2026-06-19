"""테스트용 인메모리 가짜 포트 (단일 모델: ticker는 str)."""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from collector.domain import (
    CollectionRun,
    DailyPrice,
    JobType,
    Market,
    MarketDataUnavailableError,
    RunStatus,
    Stock,
)


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


class FakeCollectionRunRepository:
    """인메모리 런 기록. finish 호출과 상태 전이를 검증할 수 있도록 보관."""

    def __init__(self) -> None:
        self.runs: dict[int, CollectionRun] = {}
        self._next_id = 1
        self.finish_calls: list[tuple[int, RunStatus]] = []

    async def start(self, job_type: JobType, markets=None) -> int:
        run_id = self._next_id
        self._next_id += 1
        self.runs[run_id] = CollectionRun(
            id=run_id,
            job_type=job_type,
            markets=",".join(m.value for m in markets) if markets else "",
            status=RunStatus.RUNNING,
            started_at=datetime.now(timezone.utc),
        )
        return run_id

    async def finish(
        self,
        run_id: int,
        status: RunStatus,
        *,
        total_stocks: int,
        succeeded: int,
        failed: int,
        rows_written: int,
        error_summary: str | None = None,
    ) -> None:
        self.finish_calls.append((run_id, status))
        run = self.runs[run_id]
        run.status = status
        run.finished_at = datetime.now(timezone.utc)
        run.total_stocks = total_stocks
        run.succeeded = succeeded
        run.failed = failed
        run.rows_written = rows_written
        run.error_summary = error_summary

    async def get(self, run_id: int) -> CollectionRun | None:
        return self.runs.get(run_id)

    async def list_recent(self, limit: int = 50) -> list[CollectionRun]:
        items = sorted(self.runs.values(), key=lambda r: r.id, reverse=True)
        return items[:limit]

    async def list_active(self) -> list[CollectionRun]:
        return [r for r in self.runs.values() if r.status is RunStatus.RUNNING]

    async def mark_orphans_interrupted(self) -> int:
        n = 0
        for r in self.runs.values():
            if r.status is RunStatus.RUNNING:
                r.status = RunStatus.INTERRUPTED
                r.finished_at = datetime.now(timezone.utc)
                n += 1
        return n


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
