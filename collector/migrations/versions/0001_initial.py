"""initial: collector schema, stocks, daily_prices (single-model)

Revision ID: 0001
Revises:
Create Date: 2026-06-19

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "collector"


def upgrade() -> None:
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")

    # 종목 마스터
    op.create_table(
        "stocks",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("ticker", sa.String(length=32), nullable=False),
        sa.Column("market", sa.String(length=16), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column(
            "is_active", sa.Boolean(), nullable=False, server_default=sa.true()
        ),
        sa.UniqueConstraint("ticker", "market", name="uq_stocks_ticker_market"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_stocks_market_active", "stocks", ["market", "is_active"], schema=SCHEMA
    )

    # 일봉 시세 (불변식은 CHECK 제약으로 강제)
    op.create_table(
        "daily_prices",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("ticker", sa.String(length=32), nullable=False),
        sa.Column("market", sa.String(length=16), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("open", sa.Numeric(20, 4), nullable=False),
        sa.Column("high", sa.Numeric(20, 4), nullable=False),
        sa.Column("low", sa.Numeric(20, 4), nullable=False),
        sa.Column("close", sa.Numeric(20, 4), nullable=False),
        sa.Column("volume", sa.BigInteger(), nullable=False),
        sa.Column(
            "collected_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "ticker", "market", "trade_date", name="uq_daily_prices_key"
        ),
        sa.CheckConstraint("high >= low", name="ck_daily_prices_high_ge_low"),
        sa.CheckConstraint(
            "open >= 0 AND high >= 0 AND low >= 0 AND close >= 0",
            name="ck_daily_prices_price_non_negative",
        ),
        sa.CheckConstraint(
            "volume >= 0", name="ck_daily_prices_volume_non_negative"
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_daily_prices_ticker_market_date",
        "daily_prices",
        ["ticker", "market", "trade_date"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_daily_prices_ticker_market_date", table_name="daily_prices", schema=SCHEMA
    )
    op.drop_table("daily_prices", schema=SCHEMA)
    op.drop_index("ix_stocks_market_active", table_name="stocks", schema=SCHEMA)
    op.drop_table("stocks", schema=SCHEMA)
    op.execute(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE")
