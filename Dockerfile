FROM python:3.12.8-slim AS builder

# Install build dependencies and git
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

# Create and activate virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir git+https://github.com/twopirllc/pandas-ta.git@development

FROM python:3.12.8-slim

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Create non-root user
RUN useradd -r -s /bin/false appuser

# Create and set permissions for numba cache directory
RUN mkdir -p /tmp/numba_cache && \
    chown -R appuser:appuser /tmp/numba_cache

# Set working directory
WORKDIR /app

# Copy application code
COPY . .

# Set proper permissions
RUN chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Add signal handling wrapper script
RUN echo '#!/bin/sh\n\
trap "exit 0" TERM INT\n\
python main.py & PID=$!\n\
wait $PID\n\
trap - TERM INT\n\
wait $PID\n\
EXIT_STATUS=$?' > /app/docker-entrypoint.sh \
    && chmod +x /app/docker-entrypoint.sh

ENTRYPOINT ["/app/docker-entrypoint.sh"]
