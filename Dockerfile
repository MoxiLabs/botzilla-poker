# Use official lightweight Python 3.12 image
FROM python:3.12-slim

# Set runtime environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TZ=Europe/Budapest

# Install system dependencies (certificates for HTTPS/WSS and timezone data)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# Create dedicated non-root user and group
RUN groupadd --gid 1000 botzilla \
    && useradd --uid 1000 --gid botzilla --shell /bin/bash --create-home botzilla

WORKDIR /app

# Install Python dependencies first for efficient layer caching
COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy application source and configurations
COPY pokerparser/ ./pokerparser/
COPY locales/ ./locales/
COPY assets/ ./assets/
COPY config.json run.py ./

# Create directories for persistent storage and logs, then grant permissions
RUN mkdir -p /app/data /app/logs /app/assets/logos \
    && chown -R botzilla:botzilla /app

# Switch to non-root user
USER botzilla

# Default command
CMD ["python", "run.py"]
