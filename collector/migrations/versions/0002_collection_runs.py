"""collection_runs: 수집 런(job run) 기록 테이블

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-19

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "collector"


def upgrade() -> None:
    op.create_table(
        "collection_runs",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("job_type", sa.String(length=16), nullable=False),
        sa.Column(
            "markets", sa.String(length=128), nullable=False, server_default=""
        ),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "total_stocks", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column("succeeded", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "rows_written", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "job_type IN ('DOMESTIC', 'OVERSEAS', 'MANUAL')",
            name="ck_collection_runs_job_type",
        ),
        sa.CheckConstraint(
            "status IN ('RUNNING', 'SUCCEEDED', 'PARTIAL', 'FAILED', 'INTERRUPTED')",
            name="ck_collection_runs_status",
        ),
        sa.CheckConstraint(
            "total_stocks >= 0 AND succeeded >= 0 AND failed >= 0 "
            "AND rows_written >= 0",
            name="ck_collection_runs_counts_non_negative",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_collection_runs_status",
        "collection_runs",
        ["status"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_collection_runs_started_at",
        "collection_runs",
        ["started_at"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_collection_runs_started_at",
        table_name="collection_runs",
        schema=SCHEMA,
    )
    op.drop_index(
        "ix_collection_runs_status",
        table_name="collection_runs",
        schema=SCHEMA,
    )
    op.drop_table("collection_runs", schema=SCHEMA)
