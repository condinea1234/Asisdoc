#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "Uso: $0 <PROJECT_ID> <REGION>"
  echo "Ejemplo: $0 evalia-ia us-central1"
  exit 1
fi

PROJECT_ID="$1"
REGION="$2"
INSTANCE_NAME="${INSTANCE_NAME:-evalia-db}"
DB_NAME="${DB_NAME:-evalia}"
DB_USER="${DB_USER:-evalia_user}"
DB_PASSWORD="${DB_PASSWORD:-EvaliaPass_2026!}"

echo "Configurando proyecto: ${PROJECT_ID}"
gcloud config set project "${PROJECT_ID}" >/dev/null

echo "Habilitando APIs SQL necesarias..."
gcloud services enable sqladmin.googleapis.com servicenetworking.googleapis.com >/dev/null

if ! gcloud sql instances describe "${INSTANCE_NAME}" >/dev/null 2>&1; then
  echo "Creando instancia Cloud SQL PostgreSQL: ${INSTANCE_NAME}"
  gcloud sql instances create "${INSTANCE_NAME}" \
    --database-version=POSTGRES_16 \
    --tier=db-f1-micro \
    --region="${REGION}" \
    --storage-size=10GB \
    --storage-auto-increase \
    --availability-type=zonal
else
  echo "La instancia ${INSTANCE_NAME} ya existe."
fi

if ! gcloud sql databases describe "${DB_NAME}" --instance="${INSTANCE_NAME}" >/dev/null 2>&1; then
  echo "Creando base de datos ${DB_NAME}"
  gcloud sql databases create "${DB_NAME}" --instance="${INSTANCE_NAME}"
else
  echo "La base ${DB_NAME} ya existe."
fi

if ! gcloud sql users describe "${DB_USER}" --instance="${INSTANCE_NAME}" >/dev/null 2>&1; then
  echo "Creando usuario ${DB_USER}"
  gcloud sql users create "${DB_USER}" --instance="${INSTANCE_NAME}" --password="${DB_PASSWORD}"
else
  echo "Actualizando contraseña de ${DB_USER}"
  gcloud sql users set-password "${DB_USER}" --instance="${INSTANCE_NAME}" --password="${DB_PASSWORD}"
fi

CONNECTION_NAME="$(gcloud sql instances describe "${INSTANCE_NAME}" --format='value(connectionName)')"
echo
echo "Cloud SQL listo:"
echo "INSTANCE_NAME=${INSTANCE_NAME}"
echo "CONNECTION_NAME=${CONNECTION_NAME}"
echo "DB_NAME=${DB_NAME}"
echo "DB_USER=${DB_USER}"
echo "DB_PASSWORD=${DB_PASSWORD}"
