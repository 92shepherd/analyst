"""CollectDailyPricesUseCase 단위 테스트 (포트는 가짜로 대체)."""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from collector.application.use_cases import (
    CollectDailyPricesCommand,
    CollectDailyPricesUseCase,
)
from collector.domain import Market

from .conftest import (
    FakeMarketData,
    FakePriceRepository,
    FakeStockRepository,
    make_price,
)


@pytest.fixture
def stocks(samsung, apple):
    return [samsung, apple]


async def test_collects_and_saves_all_markets(stocks):
    end = date(2026, 6, 19)
    data = {
        "005930": [make_price("005930", Market.KOSPI, end)],
        "AAPL": [make_price("AAPL", Market.NASDAQ, end)],
    }
    stock_repo = FakeStockRepository(stocks)
    market_data = FakeMarketData(data)
    price_repo = FakePriceRepository()
    uc = CollectDailyPricesUseCase(stock_repo, market_data, price_repo)

    result = await uc.execute(CollectDailyPricesCommand(end=end))

    assert result.total_stocks == 2
    assert result.succeeded == 2
    assert result.failed == 0
    assert result.rows_written == 2
    assert len(price_repo.saved) == 2


async def test_market_filter_applies(stocks):
    end = date(2026, 6, 19)
    stock_repo = FakeStockRepository(stocks)
    market_data = FakeMarketData({"005930": [make_price("005930", Market.KOSPI, end)]})
    price_repo = FakePriceRepository()
    uc = CollectDailyPricesUseCase(stock_repo, market_data, price_repo)

    result = await uc.execute(
        CollectDailyPricesCommand(markets=[Market.KOSPI], end=end)
    )

    assert result.total_stocks == 1
    assert [c[0] for c in market_data.calls] == ["005930"]


async def test_incremental_start_after_latest(samsung):
    end = date(2026, 6, 19)
    latest = date(2026, 6, 17)
    stock_repo = FakeStockRepository([samsung])
    market_data = FakeMarketData({"005930": [make_price("005930", Market.KOSPI, end)]})
    price_repo = FakePriceRepository(latest={"005930": latest})
    uc = CollectDailyPricesUseCase(stock_repo, market_data, price_repo)

    await uc.execute(CollectDailyPricesCommand(end=end))

    # 시작일은 최근 적재일 다음 날.
    assert market_data.calls[0][1] == latest + timedelta(days=1)


async def test_lookback_used_for_new_stock(samsung):
    end = date(2026, 6, 19)
    stock_repo = FakeStockRepository([samsung])
    market_data = FakeMarketData({"005930": []})
    price_repo = FakePriceRepository()  # 이력 없음
    uc = CollectDailyPricesUseCase(stock_repo, market_data, price_repo)

    await uc.execute(CollectDailyPricesCommand(end=end, lookback_days=10))

    assert market_data.calls[0][1] == end - timedelta(days=10)


async def test_already_up_to_date_skips_fetch(samsung):
    end = date(2026, 6, 19)
    stock_repo = FakeStockRepository([samsung])
    market_data = FakeMarketData({"005930": []})
    price_repo = FakePriceRepository(latest={"005930": end})  # 이미 최신
    uc = CollectDailyPricesUseCase(stock_repo, market_data, price_repo)

    result = await uc.execute(CollectDailyPricesCommand(end=end))

    assert result.succeeded == 1
    assert market_data.calls == []  # 조회 자체를 건너뜀
    assert result.rows_written == 0


async def test_one_failure_does_not_abort_batch(samsung):
    from collector.domain import Stock

    end = date(2026, 6, 19)
    failing = Stock(ticker="FAIL", market=Market.NASDAQ)
    stock_repo = FakeStockRepository([samsung, failing])
    market_data = FakeMarketData({"005930": [make_price("005930", Market.KOSPI, end)]})
    price_repo = FakePriceRepository()
    uc = CollectDailyPricesUseCase(stock_repo, market_data, price_repo)

    result = await uc.execute(CollectDailyPricesCommand(end=end))

    assert result.succeeded == 1
    assert result.failed == 1
    assert result.failures[0][0] == "FAIL"
