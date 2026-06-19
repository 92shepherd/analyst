"""도메인 레이어 (단일 모델: 엔티티 = SQLAlchemy ORM 모델).

Clean Architecture를 완화하여 도메인 엔티티를 ORM 모델로 통합한다.
ports/use_cases는 여전히 추상(포트)에만 의존한다.
"""
from .base import Base, SCHEMA
from .errors import (
    DomainError,
    InvalidPriceError,
    InvalidTickerError,
    MarketDataUnavailableError,
)
from .market import Country, Market
from .price import DailyPrice
from .stock import Stock

__all__ = [
    "Base",
    "SCHEMA",
    "Country",
    "Market",
    "Stock",
    "DailyPrice",
    "DomainError",
    "InvalidTickerError",
    "InvalidPriceError",
    "MarketDataUnavailableError",
]
