"""SQLAlchemy 선언형 Base + 공통 메타데이터.

단일 모델 방침: 도메인 엔티티가 곧 ORM 모델이다.
모든 테이블은 collector 스키마에 속한다(서비스별 스키마 소유).
"""
from __future__ import annotations

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

SCHEMA = "collector"


class Base(DeclarativeBase):
    # 모든 테이블 기본 스키마를 collector 로 지정.
    metadata = MetaData(schema=SCHEMA)
