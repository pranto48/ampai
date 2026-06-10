#!/bin/bash
# =============================================================================
# AmpAI Easy Install Script
# Usage:  bash install.sh
# =============================================================================
set -e

BOLD="\033[1m"; GREEN="\033[0;32m"; YELLOW="\033[1;33m"; RED="\033[0;31m"; NC="\033[0m"

echo -e "${BOLD}========================================\n  AmpAI - Automated Docker Install\n========================================${NC}"

# --- 1. Prerequisites ---
command -v docker >/dev/null || { echo -e "${RED}[ERROR] Docker not installed.${NC}"; exit 1; }
docker compose version >/dev/null 2>&1 || { echo -e "${RED}[ERROR] Docker Compose plugin not found.${NC}"; exit 1; }
echo -e "${GREEN}[OK] Docker & Docker Compose found.${NC}"

# --- 2. Generate .env ---
if [ -f ".env" ]; then
  echo -e "${YELLOW}[INFO] .env exists — skipping generation. Delete it and re-run to regenerate.${NC}"
else
  echo -e "${BOLD}[STEP 1] Generating .env with random secrets...${NC}"
  PG_PASS=$(openssl rand -hex 24)
  JWT=$(openssl rand -hex 32)
  ENC_KEY=$(openssl rand -hex 32)
  ADMIN_PASS="AmpAI-$(openssl rand -hex 8)"
  cat > .env << ENVEOF
POSTGRES_DB=ampai
POSTGRES_USER=ampai
POSTGRES_PASSWORD=${PG_PASS}
REDIS_URL=redis://agent_redis:6379/0
JWT_SECRET=${JWT}
CONFIG_ENCRYPTION_KEY=${ENC_KEY}
AMPAI_DEFAULT_ADMIN_USERNAME=admin
AMPAI_DEFAULT_ADMIN_PASSWORD=${ADMIN_PASS}
AMPAI_ENV=production
OLLAMA_BASE_URL=http://host.docker.internal:11434
ALLOWED_ORIGINS=http://localhost:1420,http://127.0.0.1:1420,tauri://localhost,http://localhost:8080,http://127.0.0.1:8080
WEB_SEARCH_PROVIDER=duckduckgo
BROWSER_AUTOMATION_ENABLED=false
BROWSER_HEADLESS=false
TERMINAL_TOOLS_ENABLED=false
TERMINAL_REQUIRE_CONFIRMATION=true
ENVEOF
  chmod 600 .env
  echo -e "${GREEN}[OK] .env created.${NC}"
fi

# --- 3. Show credentials ---
echo -e "\n${BOLD}========================================\n  Admin Credentials (save these!)\n========================================${NC}"
grep AMPAI_DEFAULT_ADMIN_USERNAME .env
grep AMPAI_DEFAULT_ADMIN_PASSWORD .env
echo -e "${BOLD}========================================${NC}\n"

# --- 4. Stop old containers ---
echo -e "${BOLD}[STEP 2] Stopping existing containers...${NC}"
docker compose down --remove-orphans 2>/dev/null || true

# --- 5. Build & start ---
echo -e "${BOLD}[STEP 3] Building & starting the stack...${NC}"
docker compose up -d --build

# --- 6. Health wait ---
echo -e "\n${BOLD}[STEP 4] Waiting for backend...${NC}"
for i in $(seq 1 40); do
  curl -sf http://localhost:8000/healthz >/dev/null 2>&1 && break
  printf "."; sleep 3
done
echo -e "\n${GREEN}[OK] Backend healthy.${NC}"

# --- 7. Summary ---
HOST_IP=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "localhost")
echo -e "\n${BOLD}========================================\n  AmpAI is running!\n========================================${NC}"
echo -e "  Web UI   : ${GREEN}http://${HOST_IP}:8080${NC}"
echo -e "  API      : ${GREEN}http://${HOST_IP}:8000${NC}"
echo -e "  ChromaDB : ${GREEN}http://${HOST_IP}:8001${NC}"
echo -e "\n  docker compose ps          # status"
echo -e "  docker compose logs -f     # live logs"
echo -e "  docker compose down        # stop all"
echo -e "${BOLD}========================================${NC}"
