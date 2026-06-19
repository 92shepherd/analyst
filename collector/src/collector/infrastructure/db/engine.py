"""DB 엔진/세션 팩토리 (SQLAlchemy 2.0 async)."""
from __future__ import annotations

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    async_sessionmaker,
    create_async_engine,
)


def create_engine(database_url: str, echo: bool = False) -> AsyncEngine:
    return create_async_engine(database_url, echo=echo, pool_pre_ping=True)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker:
    # expire_on_commit=False: 커밋 후에도 객체 속성 접근 가능.
    return async_sessionmaker(engine, expire_on_commit=False)
