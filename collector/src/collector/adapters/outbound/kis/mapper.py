"""KIS 응답(JSON dict) ↔ 도메인 모델 변환 Mapper.

KIS의 raw 응답이 도메인/유즈케이스로 새지 않도록 어댑터 경계에서만 변환한다.
일봉(output2) → DailyPrice, 요약(output1) → ValuationSnapshot.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from collector.domain import DailyPrice, InvalidPriceError, Stock, ValuationSnapshot

# 밸류에이션 BPS 유도 시 반올림 자릿수(Numeric(20,4)에 맞춤).
_BPS_QUANT = Decimal("0.0001")


def _to_decimal(raw: str | None) -> Decimal:
    if raw is None or raw == "":
        return Decimal(0)
    try:
        return Decimal(str(raw).replace(",", ""))
    except (InvalidOperation, ValueError) as exc:
        raise InvalidPriceError(f"가격 파싱 실패: {raw!r}") from exc


def _to_decimal_or_none(raw: str | None) -> Decimal | None:
    """밸류에이션용 관대한 파서: 빈 값/파싱 불가 시 None(부가 정보라 실패시키지 않음).

    KIS는 미제공 지표를 "0"으로 채워 보내기도 한다 → 의미 없는 0은 None 취급.
    """
    if raw is None or str(raw).strip() in ("", "0", "0.00"):
        return None
    try:
        return Decimal(str(raw).replace(",", ""))
    except (InvalidOperation, ValueError):
        return None


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


def map_domestic_valuation(
    stock: Stock, output1: dict, trade_date: date
) -> ValuationSnapshot | None:
    """국내주식 기간별시세 output1(요약) → ValuationSnapshot.

    output1에는 per/eps/pbr이 현재가 기준으로 들어온다(BPS는 없음).
    BPS는 PBR = 주가/BPS 관계로 주가(stck_prpr)÷PBR로 유도한다.
    유의미한 값이 하나도 없으면 None(스냅샷 미생성).

    필드: per, eps, pbr, stck_prpr
    """
    per = _to_decimal_or_none(output1.get("per"))
    pbr = _to_decimal_or_none(output1.get("pbr"))
    eps = _to_decimal_or_none(output1.get("eps"))
    price = _to_decimal_or_none(output1.get("stck_prpr"))

    bps: Decimal | None = None
    if price is not None and pbr is not None and pbr != 0:
        bps = (price / pbr).quantize(_BPS_QUANT)

    if per is None and pbr is None and eps is None and bps is None:
        return None

    return ValuationSnapshot(
        ticker=stock.ticker,
        market=stock.market,
        trade_date=trade_date,
        per=per,
        pbr=pbr,
        eps=eps,
        bps=bps,
    )
