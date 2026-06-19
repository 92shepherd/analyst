"""인바운드 어댑터: 운영/수동 트리거용 FastAPI 라우터.

외부 노출 엔드포인트는 auth-server 토큰 검증을 거쳐야 한다(미들웨어/디펜던시로 연결).
여기서는 수집 수동 트리거와 헬스체크만 제공한다.
"""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter
from pydantic import BaseModel

from collector.application.use_cases import (
    CollectDailyPricesCommand,
    CollectDailyPricesUseCase,
)
from collector.domain import Market


class CollectRequest(BaseModel):
    markets: list[Market] | None = None
    end: date | None = None
    lookback_days: int = 30
    max_concurrency: int = 5


class CollectResponse(BaseModel):
    total_stocks: int
    succeeded: int
    failed: int
    rows_written: int


def build_router(use_case: CollectDailyPricesUseCase) -> APIRouter:
    router = APIRouter()

    @router.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @router.post("/collect/daily", response_model=CollectResponse)
    async def collect_daily(req: CollectRequest) -> CollectResponse:
        result = await use_case.execute(
            CollectDailyPricesCommand(
                markets=req.markets,
                end=req.end,
                lookback_days=req.lookback_days,
                max_concurrency=req.max_concurrency,
            )
        )
        return CollectResponse(
            total_stocks=result.total_stocks,
            succeeded=result.succeeded,
            failed=result.failed,
            rows_written=result.rows_written,
        )

    return router
