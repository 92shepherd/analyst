"""Alembic 환경 (async).

- DB URL은 collector 설정(COLLECTOR_DATABASE_URL)에서 주입한다(코드 하드코딩 금지).
- target_metadata는 ORM 모델의 Base.metadata. include_schemas=True 로 collector 스키마 포함.
"""
from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from collector.domain import Base
from collector.infrastructure.config import load_settings

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 설정에서 비동기 DSN 주입.
config.set_main_option("sqlalchemy.url", load_settings().database_url)

target_metadata = Base.metadata


def do_run_migrations(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_schemas=True,  # 비기본 스키마(collector) 인식
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        include_schemas=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
