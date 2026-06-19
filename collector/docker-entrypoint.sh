#!/usr/bin/env sh
# 컨테이너 시작 시 DB 마이그레이션 적용 후 앱 기동.
set -e

echo "[entrypoint] alembic upgrade head ..."
alembic upgrade head

echo "[entrypoint] starting collector ..."
exec collector
