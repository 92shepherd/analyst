"""밸류에이션 스냅샷 엔티티 (단일 모델: 도메인 = ORM).

주가 수집 시점의 시장 밸류에이션 지표(PER/PBR/EPS/BPS)를 주가 테이블과 별개로 적재한다.
주가에 따라 매 거래일 값이 바뀌므로 (ticker, market, trade_date) 단위 1행으로 멱등 저장한다.

KIS 국내 일봉 응답 output1(요약)에서 PER/EPS/PBR을 직접 얻고, BPS는 주가÷PBR로 유도한다.
해외(나스닥/뉴욕)는 KIS가 이 지표를 제공하지 않아 스냅샷이 생성되지 않을 수 있다(best-effort).

값은 모두 nullable이다(미제공/적자 종목의 음수 PER·EPS 등 허용 — 비음수 제약을 두지 않는다).
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
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
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base
from .market import Market


class ValuationSnapshot(Base):
    __tablename__ = "valuation_snapshots"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    ticker: Mapped[str] = mapped_column(String(32), nullable=False)
    market: Mapped[Market] = mapped_column(
        Enum(Market, native_enum=False, length=16), nullable=False
    )
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    # PER·EPS는 적자 시 음수가 될 수 있어 비음수 제약을 두지 않는다.
    per: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    pbr: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    eps: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    # BPS는 KIS 일봉 응답에 직접 없어 주가÷PBR로 유도한 값(파생).
    bps: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "ticker", "market", "trade_date", name="uq_valuation_snapshots_key"
        ),
        Index(
            "ix_valuation_snapshots_ticker_market_date",
            "ticker",
            "market",
            "trade_date",
        ),
    )
