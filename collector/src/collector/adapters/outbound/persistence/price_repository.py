"""PriceRepositoryPort 구현 (Postgres, bulk upsert 적재).

단일 모델: 도메인 DailyPrice(ORM)를 그대로 사용한다.
대량 ON CONFLICT 멱등 적재를 위해 Core 스타일 pg_insert 를 사용한다.
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import async_sessionmaker

from collector.domain import DailyPrice, Stock


class SqlAlchemyPriceRepository:
    def __init__(self, session_factory: async_sessionmaker) -> None:
        self._session_factory = session_factory

    async def save_daily_prices(self, prices: list[DailyPrice]) -> int:
        if not prices:
            return 0

        rows = [
            {
                "ticker": p.ticker,
                "market": p.market,
                "trade_date": p.trade_date,
                "open": p.open,
                "high": p.high,
                "low": p.low,
                "close": p.close,
                "volume": p.volume,
            }
            for p in prices
        ]

        stmt = pg_insert(DailyPrice).values(rows)
        # (ticker, market, trade_date) 충돌 시 OHLCV 갱신 → 멱등 적재.
        stmt = stmt.on_conflict_do_update(
            constraint="uq_daily_prices_key",
            set_={
                "open": stmt.excluded.open,
                "high": stmt.excluded.high,
                "low": stmt.excluded.low,
                "close": stmt.excluded.close,
                "volume": stmt.excluded.volume,
                "collected_at": func.now(),
            },
        )

        async with self._session_factory() as session:
            async with session.begin():
                await session.execute(stmt)
        return len(rows)

    async def latest_trade_date(self, stock: Stock) -> date | None:
        stmt = select(func.max(DailyPrice.trade_date)).where(
            DailyPrice.ticker == stock.ticker,
            DailyPrice.market == stock.market,
        )
        async with self._session_factory() as session:
            return (await session.execute(stmt)).scalar_one_or_none()
