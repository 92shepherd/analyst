"""유즈케이스: 일봉 수집 (파이프라인 단계 ①).

전종목(코스피/코스닥/나스닥/뉴욕)을 대상으로 일봉을 수집하여 DB에 적재한다.
외부 시스템은 포트로만 참조하며, 구체 기술(KIS/Postgres)을 알지 못한다.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import date, timedelta

from collector.application.ports import (
    MarketDataPort,
    PriceRepositoryPort,
    StockRepositoryPort,
)
from collector.domain import Market, MarketDataUnavailableError, Stock

logger = logging.getLogger(__name__)

# 신규 종목(적재 이력 없음)에 대한 기본 소급 수집 일수.
DEFAULT_LOOKBACK_DAYS = 30


@dataclass(frozen=True)
class CollectDailyPricesCommand:
    """수집 명령.

    Attributes:
        markets: 수집 대상 시장. None이면 전 시장.
        end: 수집 종료일(기본: 오늘).
        lookback_days: 신규 종목에 대한 소급 수집 일수.
        max_concurrency: 동시에 처리할 종목 수(어댑터 레이트리밋과 별개의 상한).
    """

    markets: list[Market] | None = None
    end: date | None = None
    lookback_days: int = DEFAULT_LOOKBACK_DAYS
    max_concurrency: int = 5


@dataclass
class CollectDailyPricesResult:
    total_stocks: int = 0
    succeeded: int = 0
    failed: int = 0
    rows_written: int = 0
    failures: list[tuple[str, str]] = field(default_factory=list)  # (ticker, reason)


class CollectDailyPricesUseCase:
    def __init__(
        self,
        stock_repo: StockRepositoryPort,
        market_data: MarketDataPort,
        price_repo: PriceRepositoryPort,
    ) -> None:
        self._stock_repo = stock_repo
        self._market_data = market_data
        self._price_repo = price_repo

    async def execute(
        self, command: CollectDailyPricesCommand | None = None
    ) -> CollectDailyPricesResult:
        command = command or CollectDailyPricesCommand()
        end = command.end or date.today()

        stocks = await self._stock_repo.list_active_stocks(command.markets)
        result = CollectDailyPricesResult(total_stocks=len(stocks))
        logger.info("일봉 수집 시작: 종목 %d개, 종료일 %s", len(stocks), end)

        semaphore = asyncio.Semaphore(max(1, command.max_concurrency))
        tasks = [
            self._collect_one(stock, end, command.lookback_days, semaphore, result)
            for stock in stocks
        ]
        await asyncio.gather(*tasks)

        logger.info(
            "일봉 수집 완료: 성공 %d, 실패 %d, 적재 행 %d",
            result.succeeded,
            result.failed,
            result.rows_written,
        )
        return result

    async def _collect_one(
        self,
        stock: Stock,
        end: date,
        lookback_days: int,
        semaphore: asyncio.Semaphore,
        result: CollectDailyPricesResult,
    ) -> None:
        async with semaphore:
            try:
                start = await self._resolve_start_date(stock, end, lookback_days)
                if start > end:
                    # 이미 최신까지 적재됨 — 신규 데이터 없음.
                    result.succeeded += 1
                    return

                prices = await self._market_data.fetch_daily_prices(stock, start, end)
                written = await self._price_repo.save_daily_prices(prices)

                result.succeeded += 1
                result.rows_written += written
            except MarketDataUnavailableError as exc:
                result.failed += 1
                result.failures.append((str(stock.ticker), str(exc)))
                logger.warning("시세 조회 실패 %s: %s", stock.ticker, exc)
            except Exception as exc:  # noqa: BLE001 - 한 종목 실패가 배치 전체를 막지 않도록 격리
                result.failed += 1
                result.failures.append((str(stock.ticker), repr(exc)))
                logger.exception("종목 처리 중 예외 %s", stock.ticker)

    async def _resolve_start_date(
        self, stock: Stock, end: date, lookback_days: int
    ) -> date:
        """증분 수집 시작일 계산: 최근 적재일 다음 날, 없으면 소급 기간 시작."""
        latest = await self._price_repo.latest_trade_date(stock)
        if latest is None:
            return end - timedelta(days=lookback_days)
        return latest + timedelta(days=1)
