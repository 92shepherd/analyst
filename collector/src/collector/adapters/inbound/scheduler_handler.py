"""인바운드 어댑터: 스케줄러가 호출하는 수집 핸들러.

use case를 직접 호출하지 않고 CollectionRunService 를 경유해 실행을 런 단위로 기록한다.
국장/미장 분리는 여기서 시장 필터로 일어난다.
"""
from __future__ import annotations

import logging

from collector.application.services import CollectionRunService
from collector.application.use_cases import (
    CollectDailyPricesCommand,
    CollectDailyPricesResult,
)
from collector.domain import JobType, Market

logger = logging.getLogger(__name__)


class DailyCollectionScheduleHandler:
    """장 마감 후 전종목 일봉을 수집하는 스케줄 잡 핸들러."""

    def __init__(self, run_service: CollectionRunService) -> None:
        self._run_service = run_service

    async def run_domestic(self) -> CollectDailyPricesResult:
        """코스피/코스닥 수집(국내 장 마감 후)."""
        return await self._run_service.execute_recorded(
            JobType.DOMESTIC,
            CollectDailyPricesCommand(markets=[Market.KOSPI, Market.KOSDAQ]),
        )

    async def run_overseas(self) -> CollectDailyPricesResult:
        """나스닥/뉴욕 수집(미국 장 마감 후)."""
        return await self._run_service.execute_recorded(
            JobType.OVERSEAS,
            CollectDailyPricesCommand(markets=[Market.NASDAQ, Market.NYSE]),
        )
