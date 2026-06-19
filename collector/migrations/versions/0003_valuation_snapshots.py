"""valuation_snapshots: 주가 수집 시점 밸류에이션(PER/PBR/EPS/BPS) 스냅샷

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-19

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "collector"


def upgrade() -> None:
    op.create_table(
        "valuation_snapshots",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("ticker", sa.String(length=32), nullable=False),
        sa.Column("market", sa.String(length=16), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        # PER·EPS는 적자 종목에서 음수가 될 수 있어 비음수 제약을 두지 않는다.
        sa.Column("per", sa.Numeric(20, 4), nullable=True),
        sa.Column("pbr", sa.Numeric(20, 4), nullable=True),
        sa.Column("eps", sa.Numeric(20, 4), nullable=True),
        sa.Column("bps", sa.Numeric(20, 4), nullable=True),
        sa.Column(
            "collected_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "ticker", "market", "trade_date", name="uq_valuation_snapshots_key"
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_valuation_snapshots_ticker_market_date",
        "valuation_snapshots",
        ["ticker", "market", "trade_date"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_valuation_snapshots_ticker_market_date",
        table_name="valuation_snapshots",
        schema=SCHEMA,
    )
    op.drop_table("valuation_snapshots", schema=SCHEMA)
