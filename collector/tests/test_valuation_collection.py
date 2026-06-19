"""주가 수집 시점 밸류에이션(PER/PBR/EPS/BPS) 수집 동작 테스트.

- 국내 종목: 스냅샷 저장
- 해외 종목(밸류에이션 None): 스냅샷 미저장
- 밸류에이션 저장 실패: best-effort — 주가 수집은 성공 유지
- valuation_repo 미주입: 가격만 수집(스냅샷 무시)
- mapper: output1에서 per/eps/pbr 직접 + bps=주가/pbr 유도, 누락 처리
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from collector.adapters.outbound.kis.mapper import map_domestic_valuation
from collector.application.use_cases import (
    CollectDailyPricesCommand,
    CollectDailyPricesUseCase,
)
from collector.domain import Market, Stock

from .conftest import (
    FakeMarketData,
    FakePriceRepository,
    FakeStockRepository,
    FakeValuationRepository,
    make_price,
    make_valuation,
)


async def test_domestic_valuation_snapshot_saved(samsung):
    end = date(2026, 6, 19)
    md = FakeMarketData(
        data={"005930": [make_price("005930", Market.KOSPI, end)]},
        valuations={"005930": make_valuation("005930", Market.KOSPI, end)},
    )
    val_repo = FakeValuationRepository()
    uc = CollectDailyPricesUseCase(
        FakeStockRepository([samsung]), md, FakePriceRepository(), val_repo
    )

    result = await uc.execute(CollectDailyPricesCommand(end=end))

    assert result.succeeded == 1
    assert result.valuations_written == 1
    assert len(val_repo.saved) == 1
    snap = val_repo.saved[0]
    assert snap.ticker == "005930"
    assert snap.per == Decimal("10")
    assert snap.bps == Decimal("33333")


async def test_overseas_without_valuation_saves_no_snapshot(apple):
    end = date(2026, 6, 19)
    # 해외는 밸류에이션 None (KIS 미제공).
    md = FakeMarketData(data={"AAPL": [make_price("AAPL", Market.NASDAQ, end)]})
    val_repo = FakeValuationRepository()
    uc = CollectDailyPricesUseCase(
        FakeStockRepository([apple]), md, FakePriceRepository(), val_repo
    )

    result = await uc.execute(CollectDailyPricesCommand(end=end))

    assert result.succeeded == 1
    assert result.valuations_written == 0
    assert val_repo.saved == []


async def test_valuation_save_failure_is_best_effort(samsung):
    """밸류에이션 저장이 터져도 주가 수집은 성공으로 유지된다."""
    end = date(2026, 6, 19)
    md = FakeMarketData(
        data={"005930": [make_price("005930", Market.KOSPI, end)]},
        valuations={"005930": make_valuation("005930", Market.KOSPI, end)},
    )
    val_repo = FakeValuationRepository(fail_on={"005930"})
    price_repo = FakePriceRepository()
    uc = CollectDailyPricesUseCase(
        FakeStockRepository([samsung]), md, price_repo, val_repo
    )

    result = await uc.execute(CollectDailyPricesCommand(end=end))

    assert result.succeeded == 1
    assert result.failed == 0
    assert result.rows_written == 1  # 주가는 정상 적재
    assert result.valuations_written == 0  # 스냅샷은 실패
    assert val_repo.saved == []


async def test_no_valuation_repo_collects_prices_only(samsung):
    """valuation_repo 미주입 시 가격만 수집(스냅샷 무시), 예외 없음."""
    end = date(2026, 6, 19)
    md = FakeMarketData(
        data={"005930": [make_price("005930", Market.KOSPI, end)]},
        valuations={"005930": make_valuation("005930", Market.KOSPI, end)},
    )
    uc = CollectDailyPricesUseCase(
        FakeStockRepository([samsung]), md, FakePriceRepository()
    )  # valuation_repo 없음

    result = await uc.execute(CollectDailyPricesCommand(end=end))

    assert result.succeeded == 1
    assert result.valuations_written == 0


# ── mapper 단위 테스트 ────────────────────────────────────────────


def test_mapper_derives_bps_from_price_and_pbr():
    stock = Stock(ticker="005930", market=Market.KOSPI)
    output1 = {"per": "12.5", "pbr": "1.25", "eps": "6000", "stck_prpr": "75000"}

    snap = map_domestic_valuation(stock, output1, date(2026, 6, 19))

    assert snap is not None
    assert snap.per == Decimal("12.5")
    assert snap.pbr == Decimal("1.25")
    assert snap.eps == Decimal("6000")
    # bps = 75000 / 1.25 = 60000
    assert snap.bps == Decimal("60000.0000")


def test_mapper_handles_missing_and_zero_fields():
    stock = Stock(ticker="005930", market=Market.KOSPI)
    # pbr 누락 → bps 유도 불가(None), per만 존재.
    output1 = {"per": "8.0", "pbr": "", "eps": "0", "stck_prpr": "10000"}

    snap = map_domestic_valuation(stock, output1, date(2026, 6, 19))

    assert snap is not None
    assert snap.per == Decimal("8.0")
    assert snap.pbr is None
    assert snap.eps is None  # "0"은 미제공으로 간주 → None
    assert snap.bps is None


def test_mapper_returns_none_when_all_empty():
    stock = Stock(ticker="005930", market=Market.KOSPI)
    output1 = {"per": "", "pbr": "0", "eps": "", "stck_prpr": ""}

    assert map_domestic_valuation(stock, output1, date(2026, 6, 19)) is None
