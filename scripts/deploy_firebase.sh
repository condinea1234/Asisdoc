#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${1:-}"
BACKEND_SERVICE_NAME="${2:-evalia-api}"
BACKEND_REGION="${3:-us-central1}"

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

if [[ -n "$BACKEND_SERVICE_NAME" ]]; then
  echo "Usando backend Cloud Run: ${BACKEND_SERVICE_NAME} (${BACKEND_REGION})"
  jq \
    --arg serviceId "$BACKEND_SERVICE_NAME" \
    --arg region "$BACKEND_REGION" \
    '.hosting.rewrites = [{"source":"/api/**","run":{"serviceId":$serviceId,"region":$region}},{"source":"**","destination":"/index.html"}]' \
    firebase.json >/tmp/firebase.json.tmp
  mv /tmp/firebase.json.tmp firebase.json
fi

echo "Desplegando Firebase Hosting..."
firebase deploy --only hosting

echo
echo "Deploy de Hosting completado."
echo "Abrí la URL mostrada por Firebase en tu navegador Android/PC."
