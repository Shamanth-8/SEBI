#!/usr/bin/env bash
#
# Container entrypoint: runs the API and the dashboard together.
#
# Hugging Face Spaces exposes exactly one port, so the two processes share a
# container: FastAPI stays on an internal port and Streamlit takes the public one.
# If either dies the container exits, so the platform restarts it rather than
# leaving a half-dead Space serving a dashboard with no backend.
set -euo pipefail

APP_PORT="${PORT:-7860}"          # public — Streamlit
API_PORT="${API_PORT:-8000}"      # internal — FastAPI
export API_BASE_URL="${API_BASE_URL:-http://127.0.0.1:${API_PORT}/api/v1}"

echo "── RegGraph starting ──────────────────────────────────────"
echo "  dashboard : 0.0.0.0:${APP_PORT}"
echo "  api       : 127.0.0.1:${API_PORT}  (internal)"
echo "  mode      : ${EXTRACTION_MODE:-hybrid}"
echo "  model dir : ${MODEL_DIR:-data/models}"

cleanup() {
  echo "shutting down…"
  [[ -n "${BACKEND_PID:-}" ]] && kill "$BACKEND_PID" 2>/dev/null || true
  [[ -n "${FRONTEND_PID:-}" ]] && kill "$FRONTEND_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# ── API ─────────────────────────────────────────────────────────────────────
python -m uvicorn app.main:app --host 127.0.0.1 --port "$API_PORT" &
BACKEND_PID=$!

# Wait for it to answer before starting the dashboard, so the first page load
# doesn't render a wall of connection errors.
for i in $(seq 1 60); do
  if python -c "
import sys, urllib.request
try:
    urllib.request.urlopen('http://127.0.0.1:${API_PORT}/health', timeout=2)
except Exception:
    sys.exit(1)
" 2>/dev/null; then
    echo "  api ready after ${i}s"
    break
  fi
  if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
    echo "!! api process died during startup" >&2
    exit 1
  fi
  sleep 1
done

# ── Dashboard ───────────────────────────────────────────────────────────────
# CORS/XSRF are disabled because the Space serves the app inside an iframe,
# where Streamlit's default protections reject the connection.
streamlit run frontend/dashboard.py \
  --server.port "$APP_PORT" \
  --server.address 0.0.0.0 \
  --server.headless true \
  --server.enableCORS false \
  --server.enableXsrfProtection false \
  --server.fileWatcherType none \
  --browser.gatherUsageStats false &
FRONTEND_PID=$!

# Exit as soon as either process stops, so the platform's restart policy applies.
wait -n "$BACKEND_PID" "$FRONTEND_PID"
echo "!! a process exited — stopping the container" >&2
exit 1
