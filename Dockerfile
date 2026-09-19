# Multi-Stage / Production Dockerfile for AI-Native ERP Backend
FROM python:3.12-slim

# Prevent Python from writing .pyc files and buffer output
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    PORT=8000

WORKDIR /app

# Install minimal system runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application source and configuration
COPY src/ /app/src/
COPY alembic/ /app/alembic/
COPY alembic.ini /app/
COPY baml_src/ /app/baml_src/
COPY pyproject.toml /app/
COPY entrypoint.sh /app/

RUN chmod +x /app/entrypoint.sh

# Expose default HTTP port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=20s --timeout=5s --start-period=15s --retries=3 \
  CMD curl -f http://localhost:${PORT:-8000}/health || exit 1

ENTRYPOINT ["/app/entrypoint.sh"]
