#!/usr/bin/env bash
# Azure Container Apps へのデプロイスクリプト
# 前提: az login 済み / 必要な環境変数を export 済み
set -euo pipefail

RESOURCE_GROUP="${RESOURCE_GROUP:-gijiroku-rg}"
LOCATION="${LOCATION:-japaneast}"
ACR_NAME="${ACR_NAME:-gijirokuacr}"
ENV_NAME="${ENV_NAME:-gijiroku-env}"
TAG="${TAG:-$(git rev-parse --short HEAD)}"

: "${ANTHROPIC_API_KEY:?ANTHROPIC_API_KEY を設定してください}"
: "${OPENAI_API_KEY:?OPENAI_API_KEY を設定してください}"
: "${DATABASE_URL:?DATABASE_URL を設定してください (例: postgresql+asyncpg://...)}"
: "${JWT_SECRET:?JWT_SECRET を設定してください}"
SLACK_WEBHOOK_URL="${SLACK_WEBHOOK_URL:-}"

echo "==> リソースグループ / ACR / Container Apps 環境を作成"
az group create --name "$RESOURCE_GROUP" --location "$LOCATION" --output none
az acr create --resource-group "$RESOURCE_GROUP" --name "$ACR_NAME" --sku Basic --output none || true
az containerapp env create --name "$ENV_NAME" --resource-group "$RESOURCE_GROUP" \
  --location "$LOCATION" --output none || true

echo "==> ACR でイメージをビルド (az acr build)"
az acr build --registry "$ACR_NAME" --image "gijiroku-backend:$TAG" ./backend
az acr build --registry "$ACR_NAME" --image "gijiroku-frontend:$TAG" \
  --build-arg NEXT_PUBLIC_API_URL="${NEXT_PUBLIC_API_URL:-https://gijiroku-backend.example.com}" \
  ./frontend

ACR_SERVER="$ACR_NAME.azurecr.io"

echo "==> バックエンドをデプロイ"
az containerapp create \
  --name gijiroku-backend \
  --resource-group "$RESOURCE_GROUP" \
  --environment "$ENV_NAME" \
  --image "$ACR_SERVER/gijiroku-backend:$TAG" \
  --registry-server "$ACR_SERVER" \
  --target-port 8000 \
  --ingress external \
  --min-replicas 1 --max-replicas 3 \
  --secrets \
      anthropic-key="$ANTHROPIC_API_KEY" \
      openai-key="$OPENAI_API_KEY" \
      database-url="$DATABASE_URL" \
      jwt-secret="$JWT_SECRET" \
      slack-webhook="$SLACK_WEBHOOK_URL" \
  --env-vars \
      ANTHROPIC_API_KEY=secretref:anthropic-key \
      OPENAI_API_KEY=secretref:openai-key \
      DATABASE_URL=secretref:database-url \
      JWT_SECRET=secretref:jwt-secret \
      SLACK_WEBHOOK_URL=secretref:slack-webhook \
      APP_BASE_URL="${APP_BASE_URL:-http://localhost:3000}" \
      CORS_ORIGINS="${CORS_ORIGINS:-http://localhost:3000}" \
  --output none \
  || az containerapp update \
      --name gijiroku-backend --resource-group "$RESOURCE_GROUP" \
      --image "$ACR_SERVER/gijiroku-backend:$TAG" --output none

BACKEND_FQDN=$(az containerapp show --name gijiroku-backend --resource-group "$RESOURCE_GROUP" \
  --query properties.configuration.ingress.fqdn -o tsv)
echo "    backend: https://$BACKEND_FQDN"

echo "==> フロントエンドをデプロイ"
az containerapp create \
  --name gijiroku-frontend \
  --resource-group "$RESOURCE_GROUP" \
  --environment "$ENV_NAME" \
  --image "$ACR_SERVER/gijiroku-frontend:$TAG" \
  --registry-server "$ACR_SERVER" \
  --target-port 3000 \
  --ingress external \
  --min-replicas 1 --max-replicas 3 \
  --output none \
  || az containerapp update \
      --name gijiroku-frontend --resource-group "$RESOURCE_GROUP" \
      --image "$ACR_SERVER/gijiroku-frontend:$TAG" --output none

FRONTEND_FQDN=$(az containerapp show --name gijiroku-frontend --resource-group "$RESOURCE_GROUP" \
  --query properties.configuration.ingress.fqdn -o tsv)

echo ""
echo "デプロイ完了 🎉"
echo "  Frontend: https://$FRONTEND_FQDN"
echo "  Backend:  https://$BACKEND_FQDN"
echo ""
echo "注意: フロントエンドの NEXT_PUBLIC_API_URL はビルド時に埋め込まれます。"
echo "      バックエンドの URL 確定後、NEXT_PUBLIC_API_URL=https://$BACKEND_FQDN で再実行してください。"
echo "      また CORS_ORIGINS=https://$FRONTEND_FQDN / APP_BASE_URL=https://$FRONTEND_FQDN の再設定も必要です。"
