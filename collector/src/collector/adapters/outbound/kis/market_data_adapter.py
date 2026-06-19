"""아웃바운드 어댑터: KIS REST 시세 → MarketDataPort 구현.

국내(코스피/코스닥)와 해외(나스닥/뉴욕)를 KIS Open API로 통일 수집한다.
KIS 호출은 infrastructure의 KisApiClient를 경유한다(직접 httpx 호출 금지).
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Protocol

from collector.adapters.outbound.kis.mapper import map_domestic_row, map_overseas_row
from collector.domain import (
    DailyPrice,
    Market,
    MarketDataUnavailableError,
    Stock,
)

logger = logging.getLogger(__name__)

# 해외 시장 → KIS 거래소 코드.
_OVERSEAS_EXCHANGE_CODE: dict[Market, str] = {
    Market.NASDAQ: "NAS",
    Market.NYSE: "NYS",
}


class KisApiClient(Protocol):
    """infrastructure KIS 클라이언트가 만족해야 하는 최소 인터페이스."""

    async def get_json(
        self, path: str, *, tr_id: str, params: dict[str, str]
    ) -> dict:
        ...


class KisTrConfig(Protocol):
    """TR_ID 등 환경 의존 설정(모의/실전 분기 결과)."""

    domestic_daily_path: str
    domestic_daily_tr_id: str
    overseas_daily_path: str
    overseas_daily_tr_id: str


class KisMarketDataAdapter:
    def __init__(self, client: KisApiClient, tr: KisTrConfig) -> None:
        self._client = client
        self._tr = tr

    async def fetch_daily_prices(
        self, stock: Stock, start: date, end: date
    ) -> list[DailyPrice]:
        try:
            if stock.market.is_domestic:
                prices = await self._fetch_domestic(stock, start, end)
            else:
                prices = await self._fetch_overseas(stock, start, end)
        except MarketDataUnavailableError:
            raise
        except Exception as exc:  # 외부 응답/네트워크 오류를 도메인 예외로 매핑
            raise MarketDataUnavailableError(
                f"{stock.ticker} 일봉 조회 실패: {exc}"
            ) from exc

        # 구간 필터 + 거래일 오름차순 정렬.
        prices = [p for p in prices if start <= p.trade_date <= end]
        prices.sort(key=lambda p: p.trade_date)
        return prices

    async def _fetch_domestic(
        self, stock: Stock, start: date, end: date
    ) -> list[DailyPrice]:
        params = {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": str(stock.ticker),
            "FID_INPUT_DATE_1": start.strftime("%Y%m%d"),
            "FID_INPUT_DATE_2": end.strftime("%Y%m%d"),
            "FID_PERIOD_DIV_CODE": "D",  # 일봉
            "FID_ORG_ADJ_PRC": "0",  # 수정주가 반영
        }
        body = await self._client.get_json(
            self._tr.domestic_daily_path,
            tr_id=self._tr.domestic_daily_tr_id,
            params=params,
        )
        self._raise_on_error(body, stock)
        rows = body.get("output2") or []
        return [map_domestic_row(stock, r) for r in rows if r.get("stck_bsop_date")]

    async def _fetch_overseas(
        self, stock: Stock, start: date, end: date
    ) -> list[DailyPrice]:
        excd = _OVERSEAS_EXCHANGE_CODE.get(stock.market)
        if excd is None:
            raise MarketDataUnavailableError(
                f"지원하지 않는 해외 시장: {stock.market}"
            )
        params = {
            "AUTH": "",
            "EXCD": excd,
            "SYMB": str(stock.ticker),
            "GUBN": "0",  # 0=일, 1=주, 2=월
            "BYMD": end.strftime("%Y%m%d"),  # 기준일(이 날짜로부터 과거 N일)
            "MODP": "1",  # 수정주가 반영
        }
        body = await self._client.get_json(
            self._tr.overseas_daily_path,
            tr_id=self._tr.overseas_daily_tr_id,
            params=params,
        )
        self._raise_on_error(body, stock)
        rows = body.get("output2") or []
        return [map_overseas_row(stock, r) for r in rows if r.get("xymd")]

    @staticmethod
    def _raise_on_error(body: dict, stock: Stock) -> None:
        # KIS 공통 응답: rt_cd == "0" 이면 정상.
        rt_cd = body.get("rt_cd")
        if rt_cd is not None and rt_cd != "0":
            raise MarketDataUnavailableError(
                f"{stock.ticker} KIS 오류 rt_cd={rt_cd} msg={body.get('msg1')}"
            )
