# FastAPI Fraud Detection API with MLflow integration
FROM python:3.10-slim

# Install system dependencies and Java for PySpark
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    curl \
    wget \
    ca-certificates \
    procps && \
    mkdir -p /opt/java && \
    cd /opt/java && \
    wget -q https://github.com/adoptium/temurin11-binaries/releases/download/jdk-11.0.21%2B9/OpenJDK11U-jre_x64_linux_hotspot_11.0.21_9.tar.gz && \
    tar -xzf OpenJDK11U-jre_x64_linux_hotspot_11.0.21_9.tar.gz && \
    rm OpenJDK11U-jre_x64_linux_hotspot_11.0.21_9.tar.gz && \
    rm -rf /var/lib/apt/lists/*

# Set JAVA_HOME for PySpark
ENV JAVA_HOME=/opt/java/jdk-11.0.21+9-jre
ENV PATH="${JAVA_HOME}/bin:${PATH}"

WORKDIR /app

# CRITICAL: Copy requirements FIRST (before app code) for better layer caching
# Chỉ khi requirements.txt thay đổi mới rebuild dependencies layer
COPY requirements.txt /app/requirements.txt

# Install Python dependencies (layer này sẽ được cache nếu requirements.txt không đổi)
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy application code AFTER installing dependencies
# Khi code thay đổi, chỉ layer này rebuild, không phải dependencies
COPY ./app /app/app

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# Run FastAPI with uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
