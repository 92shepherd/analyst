"""StockRepositoryPort 구현 (Postgres, 읽기).

단일 모델: 조회 결과(Stock ORM)를 그대로 반환한다(매핑 불필요).
세션 종료 후에도 컬럼 속성 접근이 가능하도록 expire_on_commit=False 를 사용한다.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from collector.domain import Market, Stock


class SqlAlchemyStockRepository:
    def __init__(self, session_factory: async_sessionmaker) -> None:
        self._session_factory = session_factory

    async def list_active_stocks(
        self, markets: list[Market] | None = None
    ) -> list[Stock]:
        stmt = select(Stock).where(Stock.is_active.is_(True))
        if markets:
            stmt = stmt.where(Stock.market.in_(markets))

        async with self._session_factory() as session:
            return list((await session.execute(stmt)).scalars().all())
