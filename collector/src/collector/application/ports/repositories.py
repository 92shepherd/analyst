"""아웃바운드 포트: 영속성(DB) 접근.

- StockRepositoryPort: 종목 마스터(수집 대상 유니버스)를 읽는다. (마스터는 DB에 적재되어 있다고 가정)
- PriceRepositoryPort: 수집한 일봉을 적재한다.
"""
from __future__ import annotations

from datetime import date
from typing import Protocol, runtime_checkable

from collector.domain import (
    CollectionRun,
    DailyPrice,
    JobType,
    Market,
    RunStatus,
    Stock,
    ValuationSnapshot,
)


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


@runtime_checkable
class ValuationRepositoryPort(Protocol):
    async def save_snapshot(self, snapshot: ValuationSnapshot) -> None:
        """밸류에이션 스냅샷 1건을 upsert 한다.

        (ticker, market, trade_date) 유니크 키 기준 멱등 적재.
        """
        ...


@runtime_checkable
class CollectionRunRepositoryPort(Protocol):
    """수집 런(job run) 기록/조회 포트.

    런당 2번의 쓰기(시작 insert + 종료 update)와 조회로 구성된다.
    영속성 절차(세션/쿼리)는 어댑터가 담당한다.
    """

    async def start(self, job_type: JobType, markets: list[Market] | None) -> int:
        """RUNNING 상태로 런 1행을 생성하고 run_id 를 반환한다."""
        ...

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
        """런을 종료 상태로 갱신하고 집계 카운트·종료시각을 기록한다."""
        ...

    async def get(self, run_id: int) -> CollectionRun | None:
        """단일 런 조회. 없으면 None."""
        ...

    async def list_recent(self, limit: int = 50) -> list[CollectionRun]:
        """최근 런 이력(started_at 내림차순)."""
        ...

    async def list_active(self) -> list[CollectionRun]:
        """현재 실행 중(RUNNING)인 런 목록."""
        ...

    async def mark_orphans_interrupted(self) -> int:
        """기동 시점에 RUNNING 으로 남아 있는 고아 런을 INTERRUPTED 로 정리한다.

        반환값은 정리한 런 수. 단일 인스턴스 전제이므로 기동 시 RUNNING 은
        모두 직전 비정상 종료의 잔재로 간주한다.
        """
        ...
