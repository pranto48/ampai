# =============================================================================
# Stage 1: Build Dependencies
# =============================================================================
FROM python:3.11-alpine AS builder

WORKDIR /app

# Install compilation dependencies required for packages like cryptography, bcrypt, and psycopg2
RUN apk add --no-cache \
    build-base \
    libffi-dev \
    openssl-dev \
    postgresql-dev \
    git \
    cargo \
    rust

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .

# Install dependencies to a virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir -U pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# =============================================================================
# Stage 2: Minimal Runtime Image
# =============================================================================
FROM python:3.11-alpine

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV SESSION_RECALL_DB_PATH=/data/agent_data/session_recall.db
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# Install runtime system dependencies (libpq for postgresql, git and curl)
RUN apk add --no-cache libpq git curl

# Copy virtual environment from builder stage
COPY --from=builder /opt/venv /opt/venv

# Copy application source code
COPY . .

RUN mkdir -p /data/agent_data /data/uploads /data/backups
RUN sed -i 's/\r$//' /app/docker-entrypoint.sh && chmod +x /app/docker-entrypoint.sh

EXPOSE 8000

CMD ["sh", "/app/docker-entrypoint.sh"]
