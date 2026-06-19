#!/usr/bin/env bash
set -euo pipefail

python docker/wait_for_db.py

if [ "${RUN_MIGRATIONS:-0}" = "1" ]; then
  echo "Applying database migrations..."
  alembic upgrade head
fi

exec "$@"
