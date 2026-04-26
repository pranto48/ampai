FROM python:3.11-slim

WORKDIR /app

# Install backend dependencies
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

# Copy source code
COPY backend/ /app/backend/
COPY frontend/ /app/frontend/

# Runtime data dir used by the app
RUN mkdir -p /app/data

# Run from backend directory so legacy absolute imports like `from auth import ...` work
WORKDIR /app/backend

# Application listens on 8000 inside container
EXPOSE 8000

# Run FastAPI app
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
