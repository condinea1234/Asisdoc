#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${1:-}"
BACKEND_URL="${2:-}"

if [[ -z "$PROJECT_ID" ]]; then
  echo "Uso: ./scripts/deploy_firebase.sh <PROJECT_ID> [BACKEND_URL]"
  exit 1
fi

if ! command -v firebase >/dev/null 2>&1; then
  echo "No se encontró firebase CLI. Instalá con: npm i -g firebase-tools"
  exit 1
fi

echo "Configurando proyecto Firebase: $PROJECT_ID"
firebase use "$PROJECT_ID"

if [[ -n "$BACKEND_URL" ]]; then
  echo "Usando backend en: $BACKEND_URL"
  jq \
    --arg backend "$BACKEND_URL" \
    '.hosting.rewrites = [{"source":"/api/**","run":{"serviceId":"asisdoc-api","region":"us-central1"}}] | .hosting.headers += [{"source":"/config.js","headers":[{"key":"Cache-Control","value":"no-store"}]}]' \
    firebase.json >/tmp/firebase.json.tmp
  mv /tmp/firebase.json.tmp firebase.json
fi

echo "Desplegando Firebase Hosting..."
firebase deploy --only hosting

echo
echo "Deploy de Hosting completado."
echo "Abrí la URL mostrada por Firebase en tu navegador Android/PC."
