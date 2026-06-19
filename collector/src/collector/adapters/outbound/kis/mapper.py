"""KIS 응답(JSON dict) ↔ 도메인 모델 변환 Mapper.

KIS의 raw 응답이 도메인/유즈케이스로 새지 않도록 어댑터 경계에서만 변환한다.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from collector.domain import DailyPrice, InvalidPriceError, Stock


def _to_decimal(raw: str | None) -> Decimal:
    if raw is None or raw == "":
        return Decimal(0)
    try:
        return Decimal(str(raw).replace(",", ""))
    except (InvalidOperation, ValueError) as exc:
        raise InvalidPriceError(f"가격 파싱 실패: {raw!r}") from exc


def _to_int(raw: str | None) -> int:
    if raw is None or raw == "":
        return 0
    try:
        return int(Decimal(str(raw).replace(",", "")))
    except (InvalidOperation, ValueError) as exc:
        raise InvalidPriceError(f"거래량 파싱 실패: {raw!r}") from exc


def _to_date(raw: str) -> date:
    return datetime.strptime(raw.strip(), "%Y%m%d").date()


def map_domestic_row(stock: Stock, row: dict) -> DailyPrice:
    """국내주식 기간별시세 output2 한 행 → DailyPrice.

    필드: stck_bsop_date, stck_oprc, stck_hgpr, stck_lwpr, stck_clpr, acml_vol
    """
    return DailyPrice(
        ticker=stock.ticker,
        market=stock.market,
        trade_date=_to_date(row["stck_bsop_date"]),
        open=_to_decimal(row.get("stck_oprc")),
        high=_to_decimal(row.get("stck_hgpr")),
        low=_to_decimal(row.get("stck_lwpr")),
        close=_to_decimal(row.get("stck_clpr")),
        volume=_to_int(row.get("acml_vol")),
    )


def map_overseas_row(stock: Stock, row: dict) -> DailyPrice:
    """해외주식 기간별시세 output2 한 행 → DailyPrice.

    필드: xymd, open, high, low, clos, tvol
    """
    return DailyPrice(
        ticker=stock.ticker,
        market=stock.market,
        trade_date=_to_date(row["xymd"]),
        open=_to_decimal(row.get("open")),
        high=_to_decimal(row.get("high")),
        low=_to_decimal(row.get("low")),
        close=_to_decimal(row.get("clos")),
        volume=_to_int(row.get("tvol")),
    )
