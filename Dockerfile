# Multi-stage Dockerfile for Phase 1 Data Collection
# Optimized for production deployment

# Build stage
FROM python:3.11-slim as builder

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies into the image (system site-packages)
# Avoid --user so packages end up in /usr/local and are available to the
# non-root `appuser` in the final stage after copying /usr/local from the
# builder stage.
RUN pip install --no-cache-dir -r requirements.txt

# Production stage
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH=/root/.local/bin:$PATH

# Create app user
RUN useradd -m -u 1000 appuser

# Set working directory
WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy Python dependencies from builder (system location)
# Packages installed without --user live under /usr/local in the builder.
COPY --from=builder /usr/local /usr/local

# Copy application code
COPY --chown=appuser:appuser . .

# Create logs directory
RUN mkdir -p logs && chown appuser:appuser logs

# Switch to app user
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python scripts/health_check.py --once || exit 1

# Default command (can be overridden)
CMD ["python", "scripts/optimized_collection.py"]
