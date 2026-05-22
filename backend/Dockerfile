# Build stage — create virtualenv and install dependencies
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies for psycopg binary
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install --no-cache-dir -r requirements.txt


# Runtime stage — lean final image
FROM python:3.11-slim AS runtime

WORKDIR /app

# Create non-root user before copying files
RUN adduser --disabled-password --gecos '' appuser

# Copy virtualenv from builder
COPY --from=builder /opt/venv /opt/venv

# Copy application source with correct ownership
COPY --chown=appuser:appuser . .

# Add venv to PATH and switch to non-root user
ENV PATH="/opt/venv/bin:$PATH"
USER appuser

EXPOSE 8000

# Use $PORT from environment (Railway sets this dynamically), fall back to 8000
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
