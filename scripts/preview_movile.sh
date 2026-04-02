#!/usr/bin/env bash
set -euo pipefail

PORT="${PORT:-8001}"
HOST="${HOST:-0.0.0.0}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$ROOT_DIR/.preview_logs"
mkdir -p "$LOG_DIR"

API_LOG="$LOG_DIR/api.log"
TUNNEL_LOG="$LOG_DIR/tunnel.log"

cleanup() {
  local exit_code=$?
  if [[ -n "${TUNNEL_PID:-}" ]] && kill -0 "$TUNNEL_PID" 2>/dev/null; then
    kill "$TUNNEL_PID" || true
  fi
  if [[ -n "${API_PID:-}" ]] && kill -0 "$API_PID" 2>/dev/null; then
    kill "$API_PID" || true
  fi
  wait "${TUNNEL_PID:-}" 2>/dev/null || true
  wait "${API_PID:-}" 2>/dev/null || true
  echo
  echo "Preview detenido."
  exit "$exit_code"
}
trap cleanup INT TERM EXIT

echo "Iniciando API en $HOST:$PORT ..."
cd "$ROOT_DIR"
python3 -m uvicorn app.main:app --host "$HOST" --port "$PORT" >"$API_LOG" 2>&1 &
API_PID=$!

for _ in {1..40}; do
  if curl -fsS "http://127.0.0.1:$PORT/health" >/dev/null 2>&1; then
    break
  fi
  sleep 0.25
done

if ! curl -fsS "http://127.0.0.1:$PORT/health" >/dev/null 2>&1; then
  echo "No se pudo iniciar la API. Revisá: $API_LOG"
  exit 1
fi

echo "API OK. Iniciando túnel público ..."
npx --yes localtunnel --port "$PORT" >"$TUNNEL_LOG" 2>&1 &
TUNNEL_PID=$!

PUBLIC_URL=""
for _ in {1..80}; do
  if [[ -f "$TUNNEL_LOG" ]]; then
    line="$(rg "your url is:" "$TUNNEL_LOG" -m 1 || true)"
    if [[ -n "$line" ]]; then
      PUBLIC_URL="${line##*your url is: }"
      break
    fi
  fi
  sleep 0.5
done

if [[ -z "$PUBLIC_URL" ]]; then
  echo "No se pudo obtener URL pública. Revisá: $TUNNEL_LOG"
  exit 1
fi

echo
echo "=============================================="
echo "Preview móvil listo"
echo "=============================================="
echo "Demo visual (sin login):"
echo "  ${PUBLIC_URL}/demo"
echo
echo "Modo real (con login):"
echo "  ${PUBLIC_URL}/"
echo
echo "Swagger API:"
echo "  ${PUBLIC_URL}/docs"
echo "=============================================="
echo
echo "Tip Android: abrí /demo para revisar diseño rápido."
echo "Presioná Ctrl+C para detener."
echo

while true; do
  if ! kill -0 "$API_PID" 2>/dev/null; then
    echo "La API se detuvo. Revisá: $API_LOG"
    exit 1
  fi
  if ! kill -0 "$TUNNEL_PID" 2>/dev/null; then
    echo "El túnel se detuvo. Revisá: $TUNNEL_LOG"
    exit 1
  fi
  sleep 2
done
