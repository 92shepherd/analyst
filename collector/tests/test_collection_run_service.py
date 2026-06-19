"""CollectionRunService 단위 테스트 (포트는 가짜로 대체).

검증 포인트:
- 집계 결과 → 최종 상태 매핑(SUCCEEDED/PARTIAL/FAILED)
- use case 예외 시에도 finally 에서 FAILED 로 finish 보장 + 재전파
- 고아 런 정리(mark_orphans_interrupted)
"""
from __future__ import annotations

from datetime import date

import pytest

from collector.application.services import CollectionRunService
from collector.application.use_cases import (
    CollectDailyPricesCommand,
    CollectDailyPricesUseCase,
)
from collector.domain import JobType, Market, RunStatus

from .conftest import (
    FakeCollectionRunRepository,
    FakeMarketData,
    FakePriceRepository,
    FakeStockRepository,
    make_price,
)


def _service(stocks, market_data) -> tuple[CollectionRunService, FakeCollectionRunRepository]:
    run_repo = FakeCollectionRunRepository()
    uc = CollectDailyPricesUseCase(
        FakeStockRepository(stocks), market_data, FakePriceRepository()
    )
    return CollectionRunService(uc, run_repo), run_repo


async def test_all_success_marks_succeeded(samsung, apple):
    end = date(2026, 6, 19)
    md = FakeMarketData(
        {
            "005930": [make_price("005930", Market.KOSPI, end)],
            "AAPL": [make_price("AAPL", Market.NASDAQ, end)],
        }
    )
    service, run_repo = _service([samsung, apple], md)

    run_id, result = await service.execute_recorded_with_id(
        JobType.MANUAL, CollectDailyPricesCommand(end=end)
    )

    run = run_repo.runs[run_id]
    assert run.status is RunStatus.SUCCEEDED
    assert run.finished_at is not None
    assert run.total_stocks == 2
    assert run.succeeded == 2
    assert run.failed == 0
    assert run.error_summary is None
    assert result.succeeded == 2


async def test_partial_failure_marks_partial(samsung):
    from collector.domain import Stock

    end = date(2026, 6, 19)
    failing = Stock(ticker="FAIL", market=Market.NASDAQ)
    md = FakeMarketData({"005930": [make_price("005930", Market.KOSPI, end)]})
    service, run_repo = _service([samsung, failing], md)

    run_id, _ = await service.execute_recorded_with_id(
        JobType.DOMESTIC, CollectDailyPricesCommand(end=end)
    )

    run = run_repo.runs[run_id]
    assert run.status is RunStatus.PARTIAL
    assert run.succeeded == 1
    assert run.failed == 1
    assert run.error_summary is not None
    assert "FAIL" in run.error_summary


async def test_all_failure_marks_failed(samsung):
    from collector.domain import Stock

    end = date(2026, 6, 19)
    f1 = Stock(ticker="FAIL", market=Market.NASDAQ)
    md = FakeMarketData({})  # FAIL 티커는 예외, 나머지는 빈 데이터지만 여기선 FAIL만
    service, run_repo = _service([f1], md)

    run_id, _ = await service.execute_recorded_with_id(
        JobType.OVERSEAS, CollectDailyPricesCommand(end=end)
    )

    run = run_repo.runs[run_id]
    assert run.status is RunStatus.FAILED
    assert run.succeeded == 0
    assert run.failed == 1


async def test_use_case_exception_records_failed_and_reraises(samsung):
    """use case.execute 자체가 터져도 finally 에서 FAILED 로 finish 되고 예외는 재전파."""
    end = date(2026, 6, 19)

    class BoomUseCase:
        async def execute(self, command=None):
            raise RuntimeError("boom")

    run_repo = FakeCollectionRunRepository()
    service = CollectionRunService(BoomUseCase(), run_repo)

    with pytest.raises(RuntimeError, match="boom"):
        await service.execute_recorded(
            JobType.MANUAL, CollectDailyPricesCommand(end=end)
        )

    # finish 가 호출되어 RUNNING 이 남지 않아야 한다.
    assert len(run_repo.finish_calls) == 1
    run_id, status = run_repo.finish_calls[0]
    assert status is RunStatus.FAILED
    assert run_repo.runs[run_id].status is RunStatus.FAILED
    assert "boom" in (run_repo.runs[run_id].error_summary or "")


async def test_markets_serialized_into_run(samsung):
    end = date(2026, 6, 19)
    md = FakeMarketData({"005930": [make_price("005930", Market.KOSPI, end)]})
    service, run_repo = _service([samsung], md)

    run_id, _ = await service.execute_recorded_with_id(
        JobType.DOMESTIC,
        CollectDailyPricesCommand(markets=[Market.KOSPI, Market.KOSDAQ], end=end),
    )

    assert run_repo.runs[run_id].markets == "KOSPI,KOSDAQ"


async def test_mark_orphans_interrupted():
    run_repo = FakeCollectionRunRepository()
    # 두 개의 RUNNING 런을 강제로 남긴다.
    await run_repo.start(JobType.DOMESTIC, [Market.KOSPI])
    await run_repo.start(JobType.OVERSEAS, [Market.NASDAQ])

    cleaned = await run_repo.mark_orphans_interrupted()

    assert cleaned == 2
    assert all(r.status is RunStatus.INTERRUPTED for r in run_repo.runs.values())
    assert await run_repo.list_active() == []
