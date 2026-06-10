#!/usr/bin/env bash
# =============================================================================
# AmpAI Automated Installation Script
# =============================================================================

set -e
set -x

# ANSI Color Codes for beautiful terminal styling
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# Clear screen and show premium header
clear
echo -e "${BLUE}${BOLD}=====================================================================${NC}"
echo -e "${CYAN}${BOLD}                 AmpAI Auto-Installer & DB Setup                     ${NC}"
echo -e "${BLUE}${BOLD}=====================================================================${NC}"
echo ""

# Helper functions for printing status
status_info() {
    echo -e "${BLUE}[i]${NC} $1"
}
status_success() {
    echo -e "${GREEN}[✓]${NC} $1"
}
status_warn() {
    echo -e "${YELLOW}[!]${NC} $1"
}
status_error() {
    echo -e "${RED}[✗]${NC} $1"
}

# 1. Check prerequisites
status_info "Checking system requirements..."

if ! command -v docker &> /dev/null; then
    status_error "Docker is not installed. Please install Docker first."
    exit 1
fi

if ! docker info &> /dev/null; then
    status_error "Docker daemon is not running. Please start the Docker daemon."
    exit 1
fi

# Detect docker compose command (v2 vs v1)
COMPOSE_CMD=""
if docker compose version &> /dev/null; then
    COMPOSE_CMD="docker compose"
elif command -v docker-compose &> /dev/null; then
    COMPOSE_CMD="docker-compose"
else
    status_error "Docker Compose (v2 or v1) is not installed. Please install docker-compose."
    exit 1
fi

status_success "Docker & Docker Compose are available."

# 2. Setup Environment Configuration (.env)
ENV_FILE=".env"
if [ ! -f "$ENV_FILE" ]; then
    status_info "Generating configuration file (.env) with secure credentials..."
    if [ -f "setup.sh" ]; then
        chmod +x setup.sh
        # Run setup.sh silently/normally
        ./setup.sh
    else
        status_error "setup.sh not found in the current directory."
        exit 1
    fi
else
    status_warn ".env file already exists. Keeping existing credentials."
fi

# Read credentials from .env
ADMIN_USER=$(grep -E "^AMPAI_DEFAULT_ADMIN_USERNAME=" "$ENV_FILE" | cut -d'=' -f2-)
ADMIN_PASS=$(grep -E "^AMPAI_DEFAULT_ADMIN_PASSWORD=" "$ENV_FILE" | cut -d'=' -f2-)

# Default to "admin" if not found
if [ -z "$ADMIN_USER" ]; then
    ADMIN_USER="admin"
fi

# 3. Pull and Build Containers
status_info "Building and starting AmpAI containers..."
if ! $COMPOSE_CMD up -d --build; then
    status_error "Failed to start Docker containers."
    exit 1
fi

status_success "Containers started successfully."

# 4. Wait for database and backend server to become healthy
status_info "Waiting for AmpAI services to start and initialize the database..."
SERVER_CONTAINER="ampai-server"
HEALTHY=false

# Wait up to 60 seconds (30 iterations * 2 seconds)
for i in {1..30}; do
    STATUS=$(docker inspect --format='{{.State.Health.Status}}' "$SERVER_CONTAINER" 2>/dev/null || echo "starting")
    if [ "$STATUS" = "healthy" ]; then
        HEALTHY=true
        echo "" # new line after dots
        break
    fi
    echo -n "."
    sleep 2
done

if [ "$HEALTHY" = false ]; then
    echo ""
    status_warn "Container status check timed out, but the services might still be starting."
    status_warn "Check container logs with: docker logs $SERVER_CONTAINER"
else
    status_success "All services are up, healthy, and database is fully initialized!"
fi

# 5. Output connection details
echo ""
echo -e "${GREEN}${BOLD}=====================================================================${NC}"
echo -e "${GREEN}${BOLD}                    AmpAI IS READY TO USE!                           ${NC}"
echo -e "${GREEN}${BOLD}=====================================================================${NC}"
echo ""
echo -e "  ${BOLD}URL:${NC}            http://localhost:8000"
echo -e "  ${BOLD}API Docs:${NC}       http://localhost:8000/docs"
echo -e "  ${BOLD}Admin Username:${NC} ${CYAN}${ADMIN_USER}${NC}"
echo -e "  ${BOLD}Admin Password:${NC} ${YELLOW}${ADMIN_PASS}${NC}"
echo ""
echo -e "${BLUE}💡 To stop the server, run:${NC} docker compose down"
echo -e "${BLUE}💡 To view logs, run:${NC}       docker logs -f $SERVER_CONTAINER"
echo ""
echo -e "${GREEN}${BOLD}=====================================================================${NC}"
