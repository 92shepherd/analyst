"""인바운드 어댑터: 스케줄러가 호출하는 수집 핸들러."""
from __future__ import annotations

import logging

from collector.application.use_cases import (
    CollectDailyPricesCommand,
    CollectDailyPricesResult,
    CollectDailyPricesUseCase,
)
from collector.domain import Market

logger = logging.getLogger(__name__)


class DailyCollectionScheduleHandler:
    """장 마감 후 전종목 일봉을 수집하는 스케줄 잡 핸들러."""

    def __init__(self, use_case: CollectDailyPricesUseCase) -> None:
        self._use_case = use_case

    async def run_domestic(self) -> CollectDailyPricesResult:
        """코스피/코스닥 수집(국내 장 마감 후)."""
        return await self._use_case.execute(
            CollectDailyPricesCommand(markets=[Market.KOSPI, Market.KOSDAQ])
        )

    async def run_overseas(self) -> CollectDailyPricesResult:
        """나스닥/뉴욕 수집(미국 장 마감 후)."""
        return await self._use_case.execute(
            CollectDailyPricesCommand(markets=[Market.NASDAQ, Market.NYSE])
        )
