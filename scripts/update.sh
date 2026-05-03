#!/bin/bash
# AmpAI Docker Update Script
# Usage: ./scripts/update.sh [--backup-dir /path/to/backups] [--repo-url <url>]
# This script is called by the backend update API endpoint.
# It backs up current state, pulls latest code, rebuilds and restarts the container.

set -e

REPO_URL="${REPO_URL:-https://github.com/pranto48/ampai.git}"
APP_DIR="${APP_DIR:-/app}"
BACKUP_BASE="${BACKUP_BASE:-/app/data/code_backups}"
TIMESTAMP=$(date +%Y%m%dT%H%M%SZ)
BACKUP_DIR="${BACKUP_BASE}/${TIMESTAMP}"
LOG_FILE="${BACKUP_BASE}/update_${TIMESTAMP}.log"
COMPOSE_FILE="/app_host/docker-compose.yml"

mkdir -p "${BACKUP_BASE}"
exec > >(tee -a "${LOG_FILE}") 2>&1

echo "=== AmpAI Update Starting at ${TIMESTAMP} ==="
echo "REPO_URL: ${REPO_URL}"
echo "APP_DIR: ${APP_DIR}"
echo "BACKUP_DIR: ${BACKUP_DIR}"

# ── Step 1: Create code backup ────────────────────────
echo ""
echo "--- Step 1: Backing up current code ---"
mkdir -p "${BACKUP_DIR}"

# Back up backend and frontend source (not data volumes)
if [ -d "${APP_DIR}/backend" ]; then
    cp -r "${APP_DIR}/backend" "${BACKUP_DIR}/backend"
    echo "Backed up: backend/"
fi
if [ -d "${APP_DIR}/frontend" ]; then
    cp -r "${APP_DIR}/frontend" "${BACKUP_DIR}/frontend"
    echo "Backed up: frontend/"
fi

# Save current git commit hash if available
if [ -d "${APP_DIR}/../.git" ]; then
    git -C "${APP_DIR}/.." rev-parse HEAD > "${BACKUP_DIR}/git_commit.txt" 2>/dev/null || echo "unknown" > "${BACKUP_DIR}/git_commit.txt"
fi

echo "Backup created at: ${BACKUP_DIR}"
echo "BACKUP_PATH=${BACKUP_DIR}" >> /tmp/ampai_update_result.env

# ── Step 2: Pull latest code from git ─────────────────
echo ""
echo "--- Step 2: Pulling latest code from GitHub ---"

# Determine the host app directory (mounted from host)
HOST_APP_DIR="${HOST_APP_DIR:-/app_host}"

if [ -d "${HOST_APP_DIR}/.git" ]; then
    echo "Found git repo at ${HOST_APP_DIR}, pulling..."
    git -C "${HOST_APP_DIR}" fetch origin
    git -C "${HOST_APP_DIR}" reset --hard origin/main 2>/dev/null || \
    git -C "${HOST_APP_DIR}" reset --hard origin/master 2>/dev/null || \
    (git -C "${HOST_APP_DIR}" stash && git -C "${HOST_APP_DIR}" pull)
    NEW_COMMIT=$(git -C "${HOST_APP_DIR}" rev-parse HEAD)
    echo "Updated to commit: ${NEW_COMMIT}"
    echo "NEW_COMMIT=${NEW_COMMIT}" >> /tmp/ampai_update_result.env
else
    echo "No git repo found inside container. Cloning fresh to temp dir..."
    TEMP_DIR=$(mktemp -d)
    git clone --depth 1 "${REPO_URL}" "${TEMP_DIR}"
    # Copy backend and frontend
    cp -rf "${TEMP_DIR}/backend/." "${HOST_APP_DIR}/backend/"
    cp -rf "${TEMP_DIR}/frontend/." "${HOST_APP_DIR}/frontend/"
    NEW_COMMIT=$(git -C "${TEMP_DIR}" rev-parse HEAD)
    echo "Updated to commit: ${NEW_COMMIT}"
    echo "NEW_COMMIT=${NEW_COMMIT}" >> /tmp/ampai_update_result.env
    rm -rf "${TEMP_DIR}"
fi

echo "Code update complete."

# ── Step 3: Install new Python dependencies ────────────
echo ""
echo "--- Step 3: Installing new Python dependencies ---"
if [ -f "${APP_DIR}/backend/requirements.txt" ]; then
    pip install --no-cache-dir -r "${APP_DIR}/backend/requirements.txt" --quiet
    echo "Dependencies installed."
else
    echo "No requirements.txt found, skipping."
fi

echo ""
echo "=== Update Complete ==="
echo "STATUS=success" >> /tmp/ampai_update_result.env
echo "TIMESTAMP=${TIMESTAMP}" >> /tmp/ampai_update_result.env
echo "LOG_FILE=${LOG_FILE}" >> /tmp/ampai_update_result.env
