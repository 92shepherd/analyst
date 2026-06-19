"""인바운드 어댑터: 운영/수동 트리거 + 수집 작업 조회용 FastAPI 라우터.

외부 노출 엔드포인트는 auth-server 토큰 검증을 거쳐야 한다(미들웨어/디펜던시로 연결).
- POST /collect/daily : 수동 수집 트리거(런으로 기록됨)
- GET  /runs          : 최근 수집 런 이력
- GET  /runs/{id}     : 단일 런 상세
- GET  /jobs          : 스케줄 잡의 다음 실행 시각 + 현재 실행 중(RUNNING) 런
"""
from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from collector.application.ports import CollectionRunRepositoryPort
from collector.application.services import CollectionRunService
from collector.application.use_cases import CollectDailyPricesCommand
from collector.domain import CollectionRun, JobType, Market


class CollectRequest(BaseModel):
    markets: list[Market] | None = None
    end: date | None = None
    lookback_days: int = 30
    max_concurrency: int = 5


class CollectResponse(BaseModel):
    run_id: int
    total_stocks: int
    succeeded: int
    failed: int
    rows_written: int


class RunView(BaseModel):
    id: int
    job_type: JobType
    markets: str
    status: str
    started_at: datetime
    finished_at: datetime | None
    total_stocks: int
    succeeded: int
    failed: int
    rows_written: int
    error_summary: str | None

    @classmethod
    def from_domain(cls, run: CollectionRun) -> "RunView":
        return cls(
            id=run.id,
            job_type=run.job_type,
            markets=run.markets,
            status=run.status.value,
            started_at=run.started_at,
            finished_at=run.finished_at,
            total_stocks=run.total_stocks,
            succeeded=run.succeeded,
            failed=run.failed,
            rows_written=run.rows_written,
            error_summary=run.error_summary,
        )


class ScheduledJobView(BaseModel):
    id: str
    name: str | None
    next_run_time: datetime | None


class JobsView(BaseModel):
    scheduled: list[ScheduledJobView]
    active_runs: list[RunView]


def build_router(
    run_service: CollectionRunService,
    run_repo: CollectionRunRepositoryPort,
) -> APIRouter:
    router = APIRouter()

    @router.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @router.post("/collect/daily", response_model=CollectResponse)
    async def collect_daily(req: CollectRequest) -> CollectResponse:
        # 수동 트리거도 런으로 기록한다. run_id 는 service 내부에서 발급되므로
        # 여기서는 결과만 받고, 최신 MANUAL 런을 조회하지 않고 service 가 노출하도록 한다.
        run_id, result = await run_service.execute_recorded_with_id(
            JobType.MANUAL,
            CollectDailyPricesCommand(
                markets=req.markets,
                end=req.end,
                lookback_days=req.lookback_days,
                max_concurrency=req.max_concurrency,
            ),
        )
        return CollectResponse(
            run_id=run_id,
            total_stocks=result.total_stocks,
            succeeded=result.succeeded,
            failed=result.failed,
            rows_written=result.rows_written,
        )

    @router.get("/runs", response_model=list[RunView])
    async def list_runs(limit: int = 50) -> list[RunView]:
        runs = await run_repo.list_recent(limit=limit)
        return [RunView.from_domain(r) for r in runs]

    @router.get("/runs/{run_id}", response_model=RunView)
    async def get_run(run_id: int) -> RunView:
        run = await run_repo.get(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="run not found")
        return RunView.from_domain(run)

    @router.get("/jobs", response_model=JobsView)
    async def list_jobs(request: Request) -> JobsView:
        scheduler = getattr(request.app.state, "scheduler", None)
        scheduled: list[ScheduledJobView] = []
        if scheduler is not None:
            for job in scheduler.get_jobs():
                scheduled.append(
                    ScheduledJobView(
                        id=job.id,
                        name=job.name,
                        # APScheduler 3.x: 미발화 시 None(예: paused)
                        next_run_time=getattr(job, "next_run_time", None),
                    )
                )
        active = await run_repo.list_active()
        return JobsView(
            scheduled=scheduled,
            active_runs=[RunView.from_domain(r) for r in active],
        )

    return router
