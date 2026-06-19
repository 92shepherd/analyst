"""시장/거래소 enum (순수 파이썬)."""
from __future__ import annotations

from enum import Enum


class Country(str, Enum):
    KR = "KR"
    US = "US"


class Market(str, Enum):
    """수집 대상 시장."""

    KOSPI = "KOSPI"
    KOSDAQ = "KOSDAQ"
    NASDAQ = "NASDAQ"
    NYSE = "NYSE"

    @property
    def country(self) -> Country:
        return Country.KR if self in (Market.KOSPI, Market.KOSDAQ) else Country.US

    @property
    def is_domestic(self) -> bool:
        return self.country is Country.KR
