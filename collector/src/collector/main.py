"""엔트리포인트 + DI 와이어링.

레이어 조립: infrastructure(클라이언트/DB) → adapters(포트 구현) → application(유즈케이스)
→ inbound(API/스케줄러). 의존성은 안쪽(도메인)을 향한다.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI

from collector.adapters.inbound.api import build_router
from collector.adapters.inbound.scheduler_handler import DailyCollectionScheduleHandler
from collector.adapters.outbound.kis import KisMarketDataAdapter
from collector.adapters.outbound.persistence import (
    SqlAlchemyCollectionRunRepository,
    SqlAlchemyPriceRepository,
    SqlAlchemyStockRepository,
)
from collector.application.services import CollectionRunService
from collector.application.use_cases import CollectDailyPricesUseCase
from collector.infrastructure.config import Settings, load_settings
from collector.infrastructure.db import create_engine, create_session_factory
from collector.infrastructure.kis import KisClient, create_http_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class Container:
    """조립된 의존성 컨테이너."""

    settings: Settings
    http_client: httpx.AsyncClient
    engine: object
    use_case: CollectDailyPricesUseCase
    run_repo: SqlAlchemyCollectionRunRepository
    run_service: CollectionRunService
    schedule_handler: DailyCollectionScheduleHandler


def build_container(settings: Settings | None = None) -> Container:
    settings = settings or load_settings()

    # infrastructure
    http_client = create_http_client(settings)
    kis_client = KisClient(settings, http_client)
    engine = create_engine(settings.database_url)
    session_factory = create_session_factory(engine)

    # adapters (포트 구현)
    market_data = KisMarketDataAdapter(kis_client, settings)
    stock_repo = SqlAlchemyStockRepository(session_factory)
    price_repo = SqlAlchemyPriceRepository(session_factory)
    run_repo = SqlAlchemyCollectionRunRepository(session_factory)

    # application
    use_case = CollectDailyPricesUseCase(
        stock_repo=stock_repo,
        market_data=market_data,
        price_repo=price_repo,
    )
    run_service = CollectionRunService(use_case=use_case, run_repo=run_repo)
    schedule_handler = DailyCollectionScheduleHandler(run_service)

    return Container(
        settings=settings,
        http_client=http_client,
        engine=engine,
        use_case=use_case,
        run_repo=run_repo,
        run_service=run_service,
        schedule_handler=schedule_handler,
    )


def build_scheduler(container: Container) -> AsyncIOScheduler:
    s = container.settings
    scheduler = AsyncIOScheduler(timezone=s.timezone)
    scheduler.add_job(
        container.schedule_handler.run_domestic,
        CronTrigger.from_crontab(s.domestic_cron, timezone=s.timezone),
        id="collect_domestic_daily",
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        container.schedule_handler.run_overseas,
        CronTrigger.from_crontab(s.overseas_cron, timezone=s.timezone),
        id="collect_overseas_daily",
        max_instances=1,
        coalesce=True,
    )
    return scheduler


def create_app(settings: Settings | None = None) -> FastAPI:
    container = build_container(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # 비정상 종료로 RUNNING 에 남아 있던 고아 런을 INTERRUPTED 로 정리(단일 인스턴스 전제).
        orphans = await container.run_repo.mark_orphans_interrupted()
        if orphans:
            logger.warning("고아 수집 런 %d건을 INTERRUPTED 로 정리", orphans)

        scheduler = build_scheduler(container)
        # /jobs 라우터가 스케줄러를 조회할 수 있도록 app.state 에 보관.
        app.state.scheduler = scheduler
        scheduler.start()
        logger.info("collector 스케줄러 시작")
        try:
            yield
        finally:
            scheduler.shutdown(wait=False)
            await container.http_client.aclose()
            logger.info("collector 종료")

    app = FastAPI(title="collector", version="0.1.0", lifespan=lifespan)
    app.include_router(build_router(container.run_service, container.run_repo))
    return app


app = create_app()


def main() -> None:
    import uvicorn

    settings = load_settings()
    uvicorn.run(
        "collector.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
    )


if __name__ == "__main__":
    main()
