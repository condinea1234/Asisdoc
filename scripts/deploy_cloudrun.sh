#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "Uso: $0 <PROJECT_ID> <REGION>"
  echo "Ejemplo: $0 mi-proyecto us-central1"
  exit 1
fi

PROJECT_ID="$1"
REGION="$2"
SERVICE_NAME="${SERVICE_NAME:-evalia-api}"
IMAGE="gcr.io/${PROJECT_ID}/${SERVICE_NAME}:latest"
DATABASE_URL="${DATABASE_URL:-}"
INSTANCE_CONNECTION_NAME="${INSTANCE_CONNECTION_NAME:-}"

echo "Configurando proyecto gcloud: ${PROJECT_ID}"
gcloud config set project "${PROJECT_ID}" >/dev/null

echo "Habilitando APIs necesarias..."
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com >/dev/null

echo "Construyendo imagen con Cloud Build: ${IMAGE}"
gcloud builds submit --tag "${IMAGE}" .

echo "Desplegando servicio Cloud Run: ${SERVICE_NAME} (${REGION})"
deploy_args=(
  run deploy "${SERVICE_NAME}"
  --image "${IMAGE}"
  --platform managed
  --region "${REGION}"
  --allow-unauthenticated
  --set-env-vars "UPLOAD_DIR=/tmp/uploads,MATERIALS_DIR=/tmp/materials"
)

if [[ -n "${DATABASE_URL}" ]]; then
  echo "Aplicando DATABASE_URL para base persistente."
  deploy_args+=(--set-env-vars "DATABASE_URL=${DATABASE_URL}")
fi

if [[ -n "${INSTANCE_CONNECTION_NAME}" ]]; then
  echo "Conectando Cloud SQL instance: ${INSTANCE_CONNECTION_NAME}"
  deploy_args+=(--add-cloudsql-instances "${INSTANCE_CONNECTION_NAME}")
fi

gcloud "${deploy_args[@]}"

URL="$(gcloud run services describe "${SERVICE_NAME}" --platform managed --region "${REGION}" --format='value(status.url)')"
echo
echo "Cloud Run listo:"
echo "${URL}"
echo
echo "Siguiente paso:"
echo "firebase hosting:channel:deploy preview --project ${PROJECT_ID}"
