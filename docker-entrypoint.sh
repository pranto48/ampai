#!/usr/bin/env sh
set -eu

if [ -f /app/main.py ]; then
  cd /app
  exec uvicorn main:app --host 0.0.0.0 --port "${PORT:-8000}"
fi

if [ -f /app/backend/main.py ]; then
  cd /app
  exec uvicorn backend.main:app --host 0.0.0.0 --port "${PORT:-8000}"
fi

echo "AmpAI startup failed: could not find /app/main.py or /app/backend/main.py" >&2
ls -la /app >&2 || true
exit 1
