#!/bin/sh
# nginx (:PORT) → uvicorn (127.0.0.1:APP_PORT); API down → branded maintenance.html
# Optional: Redis-backed media_worker when STUDIO_REDIS_URL / REDIS_URL is set.
set -eu
PORT="${PORT:-8787}"
APP_PORT="${STUDIO_APP_PORT:-8788}"
WORKERS="${UVICORN_WORKERS:-2}"
# Cap workers — each holds its own pool when Redis is off; 2–4 is typical.
case "$WORKERS" in
  ''|*[!0-9]*) WORKERS=2 ;;
esac
if [ "$WORKERS" -lt 1 ]; then WORKERS=1; fi
if [ "$WORKERS" -gt 4 ]; then WORKERS=4; fi

CONF_TMP="/tmp/studio-nginx.conf"
sed "s/listen 8787;/listen ${PORT};/" /etc/nginx/conf.d/studio.conf.template \
  | sed "s/127\\.0\\.0\\.1:8788/127.0.0.1:${APP_PORT}/" > "$CONF_TMP"
rm -f /etc/nginx/sites-enabled/default /etc/nginx/conf.d/default.conf 2>/dev/null || true
cp "$CONF_TMP" /etc/nginx/conf.d/default.conf

run_api() {
  cd /app
  export PYTHONPATH="/app/studio/server:/app"
  exec uvicorn app:app \
    --host 127.0.0.1 \
    --port "${APP_PORT}" \
    --app-dir /app/studio/server \
    --workers "${WORKERS}"
}

# Optional media worker (Redis). Falls back silently when Redis unset.
WORKER_PID=""
if [ -n "${STUDIO_REDIS_URL:-${REDIS_URL:-}}" ]; then
  if id studio >/dev/null 2>&1; then
    su -s /bin/sh studio -c "cd /app && PYTHONPATH=/app/studio/server:/app python -m media_worker" &
  else
    (cd /app && PYTHONPATH=/app/studio/server:/app python -m media_worker) &
  fi
  WORKER_PID=$!
  echo "[studio] media_worker pid=${WORKER_PID}" >&2
fi

if id studio >/dev/null 2>&1; then
  su -s /bin/sh studio -c "cd /app && PYTHONPATH=/app/studio/server:/app UVICORN_WORKERS=${WORKERS} uvicorn app:app --host 127.0.0.1 --port ${APP_PORT} --app-dir /app/studio/server --workers ${WORKERS}" &
else
  UVICORN_WORKERS="${WORKERS}" uvicorn app:app --host 127.0.0.1 --port "$APP_PORT" --app-dir /app/studio/server --workers "$WORKERS" &
fi
APP_PID=$!
echo "[studio] uvicorn workers=${WORKERS} pid=${APP_PID}" >&2

i=0
while [ "$i" -lt 60 ]; do
  if curl -fsS "http://127.0.0.1:${APP_PORT}/api/health" >/dev/null 2>&1; then
    break
  fi
  i=$((i + 1))
  sleep 0.5
done

nginx -g 'daemon off;' &
NGINX_PID=$!

term() {
  kill -TERM "$NGINX_PID" "$APP_PID" 2>/dev/null || true
  if [ -n "$WORKER_PID" ]; then
    kill -TERM "$WORKER_PID" 2>/dev/null || true
  fi
  wait "$NGINX_PID" "$APP_PID" 2>/dev/null || true
  if [ -n "$WORKER_PID" ]; then
    wait "$WORKER_PID" 2>/dev/null || true
  fi
}
trap term INT TERM

while kill -0 "$APP_PID" 2>/dev/null && kill -0 "$NGINX_PID" 2>/dev/null; do
  sleep 2
done
term
exit 1
