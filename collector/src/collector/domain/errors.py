"""도메인/애플리케이션 공통 예외."""
from __future__ import annotations


class DomainError(Exception):
    """도메인 규칙 위반."""


class InvalidTickerError(DomainError):
    pass


class InvalidPriceError(DomainError):
    pass


class MarketDataUnavailableError(DomainError):
    """외부 시세를 가져오지 못함(어댑터에서 매핑하여 발생)."""
