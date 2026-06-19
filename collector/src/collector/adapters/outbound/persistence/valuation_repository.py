"""ValuationRepositoryPort 구현 (Postgres, upsert 적재).

단일 모델: 도메인 ValuationSnapshot(ORM)을 그대로 사용한다.
(ticker, market, trade_date) 충돌 시 지표·collected_at 갱신 → 멱등 적재.
"""
from __future__ import annotations

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.sql import func

from collector.domain import ValuationSnapshot


class SqlAlchemyValuationRepository:
    def __init__(self, session_factory: async_sessionmaker) -> None:
        self._session_factory = session_factory

    async def save_snapshot(self, snapshot: ValuationSnapshot) -> None:
        values = {
            "ticker": snapshot.ticker,
            "market": snapshot.market,
            "trade_date": snapshot.trade_date,
            "per": snapshot.per,
            "pbr": snapshot.pbr,
            "eps": snapshot.eps,
            "bps": snapshot.bps,
        }
        stmt = pg_insert(ValuationSnapshot).values(**values)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_valuation_snapshots_key",
            set_={
                "per": stmt.excluded.per,
                "pbr": stmt.excluded.pbr,
                "eps": stmt.excluded.eps,
                "bps": stmt.excluded.bps,
                "collected_at": func.now(),
            },
        )
        async with self._session_factory() as session:
            async with session.begin():
                await session.execute(stmt)
