FROM python:3.11-slim

WORKDIR /app

# Copy dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY backend/ ./backend/
COPY frontend/ ./frontend/

# Set working directory to backend to run main.py
WORKDIR /app/backend

# Create a data directory for sqlite
RUN mkdir -p /app/data

# Expose port
EXPOSE 8000

# Run FastAPI app
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
