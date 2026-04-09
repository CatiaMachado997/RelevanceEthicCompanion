# Build stage — install dependencies
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies for psycopg binary
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt


# Runtime stage — lean final image
FROM python:3.11-slim AS runtime

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /root/.local /root/.local

# Copy application source
COPY . .

# Ensure scripts in .local are in PATH
ENV PATH=/root/.local/bin:$PATH

EXPOSE 8000

# Uvicorn with a single worker — Cloud Run scales via instances, not workers
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
