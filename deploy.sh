#!/bin/bash
# ============================================
# Deploy Nutrition Tracker to Google Cloud Run
# ============================================

set -e

# Конфигурация (можно переопределить через переменные окружения)
PROJECT_ID="${PROJECT_ID:-nutrition-bot-prod}"
SERVICE_NAME="${SERVICE_NAME:-nutrition-bot}"
REGION="${REGION:-us-central1}"

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}"
echo "╔═══════════════════════════════════════════════════╗"
echo "║     🍎 NUTRITION TRACKER - CLOUD RUN DEPLOY 🍎    ║"
echo "╚═══════════════════════════════════════════════════╝"
echo -e "${NC}"

# Проверяем gcloud
if ! command -v gcloud &> /dev/null; then
    echo -e "${RED}❌ gcloud CLI не установлен!${NC}"
    echo "Установи: https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# Проверяем авторизацию
echo -e "${YELLOW}🔑 Проверяю авторизацию...${NC}"
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | head -n1 | grep -q "@"; then
    echo -e "${YELLOW}Требуется авторизация...${NC}"
    gcloud auth login
fi

# Устанавливаем проект
echo -e "${YELLOW}📁 Устанавливаю проект: ${PROJECT_ID}${NC}"
gcloud config set project $PROJECT_ID 2>/dev/null || {
    echo -e "${YELLOW}Проект не существует, создаю...${NC}"
    gcloud projects create $PROJECT_ID --name="Nutrition Tracker" 2>/dev/null || true
    gcloud config set project $PROJECT_ID
}

# Включаем API
# aiplatform не нужен: используется Gemini API напрямую (GOOGLE_GENAI_USE_VERTEXAI=FALSE)
echo -e "${YELLOW}🔧 Включаю необходимые API...${NC}"
gcloud services enable run.googleapis.com --quiet
gcloud services enable cloudbuild.googleapis.com --quiet

# Запрашиваем секреты если не заданы
if [ -z "$GOOGLE_API_KEY" ]; then
    echo -e "${YELLOW}🔐 Введи GOOGLE_API_KEY:${NC}"
    read -s GOOGLE_API_KEY
fi

if [ -z "$TELEGRAM_BOT_TOKEN" ]; then
    echo -e "${YELLOW}🔐 Введи TELEGRAM_BOT_TOKEN:${NC}"
    read -s TELEGRAM_BOT_TOKEN
fi

if [ -z "$TURSO_URL" ]; then
    echo -e "${YELLOW}🔐 Введи TURSO_URL:${NC}"
    read -s TURSO_URL
fi

if [ -z "$TURSO_TOKEN" ]; then
    echo -e "${YELLOW}🔐 Введи TURSO_TOKEN:${NC}"
    read -s TURSO_TOKEN
fi

# SESSION_DB_URL (Neon Postgres) опционален: без него сессии InMemory
# и теряются при рестарте/масштабировании
EXTRA_ENV_FLAGS=()
if [ -n "$SESSION_DB_URL" ]; then
    EXTRA_ENV_FLAGS+=(--update-env-vars="SESSION_DB_URL=$SESSION_DB_URL")
else
    echo -e "${YELLOW}⚠️ SESSION_DB_URL не задан — сессии будут InMemory (теряются при рестарте)${NC}"
fi

# Первый деплой (без WEBHOOK_URL)
echo -e "${GREEN}🚀 Деплою на Cloud Run...${NC}"
gcloud run deploy $SERVICE_NAME \
    --source . \
    --region=$REGION \
    --allow-unauthenticated \
    --update-env-vars="GOOGLE_API_KEY=$GOOGLE_API_KEY" \
    --update-env-vars="TELEGRAM_BOT_TOKEN=$TELEGRAM_BOT_TOKEN" \
    --update-env-vars="TURSO_URL=$TURSO_URL" \
    --update-env-vars="TURSO_TOKEN=$TURSO_TOKEN" \
    --update-env-vars="GOOGLE_CLOUD_PROJECT=$PROJECT_ID" \
    --update-env-vars="GOOGLE_CLOUD_LOCATION=$REGION" \
    --update-env-vars="GOOGLE_GENAI_USE_VERTEXAI=FALSE" \
    "${EXTRA_ENV_FLAGS[@]}" \
    --memory=1Gi \
    --cpu=2 \
    --min-instances=0 \
    --max-instances=3 \
    --cpu-boost \
    --timeout=300

# Получаем URL сервиса
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region=$REGION --format="value(status.url)")

echo -e "${GREEN}✅ Сервис задеплоен: ${SERVICE_URL}${NC}"

# Обновляем с WEBHOOK_URL
# ВАЖНО: --update-env-vars, а не --set-env-vars — последний СТИРАЕТ все
# остальные переменные сервиса, оставляя только перечисленные
echo -e "${YELLOW}🔗 Устанавливаю WEBHOOK_URL...${NC}"
gcloud run services update $SERVICE_NAME \
    --region=$REGION \
    --update-env-vars="WEBHOOK_URL=$SERVICE_URL"

echo ""
echo -e "${GREEN}╔═══════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║              ✅ ДЕПЛОЙ ЗАВЕРШЁН!                  ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "🌐 URL сервиса: ${GREEN}${SERVICE_URL}${NC}"
echo -e "🤖 Webhook URL: ${GREEN}${SERVICE_URL}/webhook${NC}"
echo ""
echo -e "${YELLOW}Проверь бота в Telegram!${NC}"

