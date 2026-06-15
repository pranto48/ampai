# =============================================================================
# Stage 1: Build Dependencies
# =============================================================================
FROM python:3.11-slim AS builder

WORKDIR /app

# Install compilation dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .

# Install dependencies to a virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple -U pip setuptools wheel && \
    pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt

# =============================================================================
# Stage 2: Minimal Runtime Image
# =============================================================================
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV SESSION_RECALL_DB_PATH=/data/agent_data/session_recall.db
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# Install runtime system dependencies (libpq, git, curl, and static docker client)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    git \
    curl \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://download.docker.com/linux/static/stable/x86_64/docker-24.0.7.tgz | tar -xz -C /tmp && \
    mv /tmp/docker/docker /usr/local/bin/docker && \
    rm -rf /tmp/docker

# Copy virtual environment from builder stage
COPY --from=builder /opt/venv /opt/venv

# Copy application source code
COPY . .

RUN mkdir -p /data/agent_data /data/uploads /data/backups
RUN sed -i 's/\r$//' /app/docker-entrypoint.sh && chmod +x /app/docker-entrypoint.sh

EXPOSE 8000

CMD ["sh", "/app/docker-entrypoint.sh"]

