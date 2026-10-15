#!/bin/sh
# nginx (:PORT) → uvicorn (127.0.0.1:APP_PORT); API down → branded maintenance.html
set -eu
PORT="${PORT:-8787}"
APP_PORT="${STUDIO_APP_PORT:-8788}"

CONF_TMP="/tmp/studio-nginx.conf"
sed "s/listen 8787;/listen ${PORT};/" /etc/nginx/conf.d/studio.conf.template \
  | sed "s/127\\.0\\.0\\.1:8788/127.0.0.1:${APP_PORT}/" > "$CONF_TMP"
rm -f /etc/nginx/conf.d/default.conf
cp "$CONF_TMP" /etc/nginx/conf.d/default.conf

# Start API as studio user when possible
if id studio >/dev/null 2>&1; then
  su -s /bin/sh studio -c "cd /app && PYTHONPATH=/app/studio/server:/app uvicorn app:app --host 127.0.0.1 --port ${APP_PORT} --app-dir /app/studio/server" &
else
  uvicorn app:app --host 127.0.0.1 --port "$APP_PORT" --app-dir /app/studio/server &
fi
APP_PID=$!

i=0
while [ "$i" -lt 40 ]; do
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
  wait "$NGINX_PID" "$APP_PID" 2>/dev/null || true
}
trap term INT TERM

while kill -0 "$APP_PID" 2>/dev/null && kill -0 "$NGINX_PID" 2>/dev/null; do
  sleep 2
done
term
exit 1
