"""KIS 응답 → 도메인 모델 Mapper 테스트."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from collector.adapters.outbound.kis.mapper import map_domestic_row, map_overseas_row
from collector.domain import Market, Stock


def test_map_domestic_row():
    stock = Stock(ticker="005930", market=Market.KOSPI)
    row = {
        "stck_bsop_date": "20260619",
        "stck_oprc": "80000",
        "stck_hgpr": "81000",
        "stck_lwpr": "79500",
        "stck_clpr": "80500",
        "acml_vol": "12345678",
    }
    p = map_domestic_row(stock, row)
    assert p.trade_date == date(2026, 6, 19)
    assert p.open == Decimal("80000")
    assert p.close == Decimal("80500")
    assert p.volume == 12345678


def test_map_overseas_row_with_decimals_and_commas():
    stock = Stock(ticker="AAPL", market=Market.NASDAQ)
    row = {
        "xymd": "20260619",
        "open": "195.12",
        "high": "198.40",
        "low": "194.00",
        "clos": "197.55",
        "tvol": "55,000,000",
    }
    p = map_overseas_row(stock, row)
    assert p.trade_date == date(2026, 6, 19)
    assert p.high == Decimal("198.40")
    assert p.volume == 55000000
