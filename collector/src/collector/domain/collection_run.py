"""수집 런(job run) 엔티티 (단일 모델: 도메인 = ORM).

collector가 떠 있는 동안 수행한/수행 중인 수집 실행을 런 단위(1행/실행)로 기록한다.
스케줄 잡과 수동 트리거가 동일 경로(CollectionRunService)로 이 테이블에 적재한다.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Enum as SAEnum,
    Identity,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class JobType(str, Enum):
    """런을 발생시킨 트리거 종류."""

    DOMESTIC = "DOMESTIC"  # 국장 스케줄 잡(코스피/코스닥)
    OVERSEAS = "OVERSEAS"  # 미장 스케줄 잡(나스닥/뉴욕)
    MANUAL = "MANUAL"  # 수동 트리거(POST /collect/daily)


class RunStatus(str, Enum):
    """런 진행/결과 상태."""

    RUNNING = "RUNNING"  # 실행 중
    SUCCEEDED = "SUCCEEDED"  # 전 종목 성공(실패 0)
    PARTIAL = "PARTIAL"  # 일부 종목 실패
    FAILED = "FAILED"  # 전부 실패 또는 실행 자체 예외
    INTERRUPTED = "INTERRUPTED"  # 비정상 종료로 RUNNING에 남았던 런(기동 시 정리)


class CollectionRun(Base):
    __tablename__ = "collection_runs"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    job_type: Mapped[JobType] = mapped_column(
        SAEnum(JobType, native_enum=False, length=16), nullable=False
    )
    # 요청 시장 목록(예: "KOSPI,KOSDAQ"). 전 시장이면 빈 문자열.
    markets: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    status: Mapped[RunStatus] = mapped_column(
        SAEnum(RunStatus, native_enum=False, length=16),
        nullable=False,
        default=RunStatus.RUNNING,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    total_stocks: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    succeeded: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rows_written: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_collection_runs_status", "status"),
        Index("ix_collection_runs_started_at", "started_at"),
        CheckConstraint(
            "total_stocks >= 0 AND succeeded >= 0 AND failed >= 0 AND rows_written >= 0",
            name="ck_collection_runs_counts_non_negative",
        ),
    )

    @property
    def is_active(self) -> bool:
        return self.status is RunStatus.RUNNING
