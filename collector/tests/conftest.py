"""테스트용 인메모리 가짜 포트 (단일 모델: ticker는 str)."""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from collector.application.ports import DailyMarketData
from collector.domain import (
    CollectionRun,
    DailyPrice,
    JobType,
    Market,
    MarketDataUnavailableError,
    RunStatus,
    Stock,
    ValuationSnapshot,
)


class FakeStockRepository:
    def __init__(self, stocks: list[Stock]) -> None:
        self._stocks = stocks

    async def list_active_stocks(self, markets=None) -> list[Stock]:
        if markets is None:
            return list(self._stocks)
        return [s for s in self._stocks if s.market in markets]


class FakeMarketData:
    """종목별로 미리 정해둔 일봉(+선택적 밸류에이션)을 반환. 'FAIL' 티커는 예외.

    valuations: 티커 → ValuationSnapshot. 지정 시 해당 종목의 fetch_daily가 스냅샷도 반환.
    """

    def __init__(
        self,
        data: dict[str, list[DailyPrice]],
        valuations: dict[str, ValuationSnapshot] | None = None,
    ) -> None:
        self._data = data
        self._valuations = valuations or {}
        self.calls: list[tuple[str, date, date]] = []

    async def fetch_daily(
        self, stock: Stock, start: date, end: date
    ) -> DailyMarketData:
        self.calls.append((stock.ticker, start, end))
        if stock.ticker == "FAIL":
            raise MarketDataUnavailableError("의도된 실패")
        rows = self._data.get(stock.ticker, [])
        prices = [p for p in rows if start <= p.trade_date <= end]
        return DailyMarketData(
            prices=prices, valuation=self._valuations.get(stock.ticker)
        )


class FakeValuationRepository:
    """인메모리 밸류에이션 스냅샷 저장. fail_on 티커는 저장 시 예외(best-effort 검증용)."""

    def __init__(self, fail_on: set[str] | None = None) -> None:
        self.saved: list[ValuationSnapshot] = []
        self._fail_on = fail_on or set()

    async def save_snapshot(self, snapshot: ValuationSnapshot) -> None:
        if snapshot.ticker in self._fail_on:
            raise RuntimeError("의도된 밸류에이션 저장 실패")
        self.saved.append(snapshot)


def make_valuation(
    ticker: str, market: Market, d: date, per="10", pbr="1.5", eps="5000", bps="33333"
) -> ValuationSnapshot:
    from decimal import Decimal

    return ValuationSnapshot(
        ticker=ticker,
        market=market,
        trade_date=d,
        per=Decimal(per) if per is not None else None,
        pbr=Decimal(pbr) if pbr is not None else None,
        eps=Decimal(eps) if eps is not None else None,
        bps=Decimal(bps) if bps is not None else None,
    )


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
        run.finis