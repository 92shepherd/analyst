"""종목 엔티티 (단일 모델: 도메인 = ORM).

종목 마스터는 외부 잡이 적재한다고 가정하고, collector는 읽기 위주로 사용한다.
"""
from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, Enum, Identity, Index, String, UniqueConstraint, true
from sqlalchemy.orm import Mapped, mapped_column, validates

from .base import Base
from .errors import InvalidTickerError
from .market import Market


class Stock(Base):
    __tablename__ = "stocks"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    # 국내: 6자리 단축코드(예: '005930'), 해외: 거래소 심볼(예: 'AAPL')
    ticker: Mapped[str] = mapped_column(String(32), nullable=False)
    market: Mapped[Market] = mapped_column(
        Enum(Market, native_enum=False, length=16), nullable=False
    )
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=true()
    )

    __table_args__ = (
        UniqueConstraint("ticker", "market", name="uq_stocks_ticker_market"),
        Index("ix_stocks_market_active", "market", "is_active"),
    )

    @property
    def is_domestic(self) -> bool:
        return self.market.is_domestic

    @validates("ticker")
    def _validate_ticker(self, _key: str, value: str) -> str:
        v = (value or "").strip()
        if not v:
            raise InvalidTickerError("티커는 비어 있을 수 없습니다.")
        return v
