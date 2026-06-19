"""CollectionRunRepositoryPort 구현 (Postgres).

단일 모델: 도메인 CollectionRun(ORM)을 그대로 적재/조회한다.
markets 목록은 어댑터 경계에서 콤마 문자열로 직렬화한다(도메인 컬럼은 str).
"""
from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.sql import func

from collector.domain import CollectionRun, JobType, Market, RunStatus


def _serialize_markets(markets: list[Market] | None) -> str:
    """시장 목록을 'KOSPI,KOSDAQ' 형태로 직렬화. None/빈 목록은 전 시장(빈 문자열)."""
    if not markets:
        return ""
    return ",".join(m.value for m in markets)


class SqlAlchemyCollectionRunRepository:
    def __init__(self, session_factory: async_sessionmaker) -> None:
        self._session_factory = session_factory

    async def start(self, job_type: JobType, markets: list[Market] | None) -> int:
        run = CollectionRun(
            job_type=job_type,
            markets=_serialize_markets(markets),
            status=RunStatus.RUNNING,
        )
        async with self._session_factory() as session:
            async with session.begin():
                session.add(run)
            # begin() 컨텍스트 종료 시 커밋 → Identity PK 채워짐.
            return run.id

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
        stmt = (
            update(CollectionRun)
            .where(CollectionRun.id == run_id)
            .values(
                status=status,
                finished_at=func.now(),
                total_stocks=total_stocks,
                succeeded=succeeded,
                failed=failed,
                rows_written=rows_written,
                error_summary=error_summary,
            )
        )
        async with self._session_factory() as session:
            async with session.begin():
                await session.execute(stmt)

    async def get(self, run_id: int) -> CollectionRun | None:
        stmt = select(CollectionRun).where(CollectionRun.id == run_id)
        async with self._session_factory() as session:
            return (await session.execute(stmt)).scalar_one_or_none()

    async def list_recent(self, limit: int = 50) -> list[CollectionRun]:
        stmt = (
            select(CollectionRun)
            .order_by(CollectionRun.started_at.desc(), CollectionRun.id.desc())
            .limit(limit)
        )
        async with self._session_factory() as session:
            return list((await session.execute(stmt)).scalars().all())

    async def list_active(self) -> list[CollectionRun]:
        stmt = (
            select(CollectionRun)
            .where(CollectionRun.status == RunStatus.RUNNING)
            .order_by(CollectionRun.started_at.desc())
        )
        async with self._session_factory() as session:
            return list((await session.execute(stmt)).scalars().all())

    async def mark_orphans_interrupted(self) -> int:
        stmt = (
            update(CollectionRun)
            .where(CollectionRun.status == RunStatus.RUNNING)
            .values(status=RunStatus.INTERRUPTED, finished_at=func.now())
        )
        async with self._session_factory() as session:
            async with session.begin():
                result = await session.execute(stmt)
        return result.rowcount or 0
