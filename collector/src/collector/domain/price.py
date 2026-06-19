"""일봉(OHLCV) 엔티티 (단일 모델: 도메인 = ORM).

가격 불변식은 DB CHECK 제약으로 강제하고, 음수 방지는 @validates 로 조기 차단한다.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    Identity,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, validates

from .base import Base
from .errors import InvalidPriceError
from .market import Market


class DailyPrice(Base):
    __tablename__ = "daily_prices"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    ticker: Mapped[str] = mapped_column(String(32), nullable=False)
    market: Mapped[Market] = mapped_column(
        Enum(Market, native_enum=False, length=16), nullable=False
    )
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    open: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    high: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    low: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    close: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    volume: Mapped[int] = mapped_column(BigInteger, nullable=False)
    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("ticker", "market", "trade_date", name="uq_daily_prices_key"),
        Index("ix_daily_prices_ticker_market_date", "ticker", "market", "trade_date"),
        CheckConstraint("high >= low", name="ck_daily_prices_high_ge_low"),
        CheckConstraint(
            "open >= 0 AND high >= 0 AND low >= 0 AND close >= 0",
            name="ck_daily_prices_price_non_negative",
        ),
        CheckConstraint("volume >= 0", name="ck_daily_prices_volume_non_negative"),
    )

    @validates("open", "high", "low", "close")
    def _validate_price(self, key: str, value: Decimal) -> Decimal:
        if value is not None and value < 0:
            raise InvalidPriceError(f"{key} 가격은 음수일 수 없습니다: {value}")
        return value

    @validates("volume")
    def _validate_volume(self, _key: str, value: int) -> int:
        if value is not None and value < 0:
            raise InvalidPriceError(f"거래량은 음수일 수 없습니다: {value}")
        return value
