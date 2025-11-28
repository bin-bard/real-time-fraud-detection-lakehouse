#!/usr/bin/env bash

# MLflow Server Startup Script
# Starts MLflow tracking server with PostgreSQL backend and S3 artifact storage

set -e

echo "🚀 Starting MLflow Server..."
echo "📊 Backend Store: $MLFLOW_BACKEND_STORE_URI"
echo "🗃️  Artifact Store: $MLFLOW_DEFAULT_ARTIFACT_ROOT"
echo "🌐 S3 Endpoint: $MLFLOW_S3_ENDPOINT_URL"

# Wait for database to be ready
echo "⏳ Waiting for MLflow database to be ready..."
while ! nc -z mlflow-db 5432; do
    echo "   Database not ready, waiting 2 seconds..."
    sleep 2
done
echo "✅ Database is ready!"

# Initialize database tables if needed
echo "🔧 Initializing MLflow database schema..."
mlflow db upgrade "$MLFLOW_BACKEND_STORE_URI" || {
    echo "⚠️  Database upgrade failed, but continuing..."
}

# Start MLflow server
echo "🎉 Starting MLflow tracking server on port 5000..."
exec mlflow server \
    --backend-store-uri "$MLFLOW_BACKEND_STORE_URI" \
    --default-artifact-root "$MLFLOW_DEFAULT_ARTIFACT_ROOT" \
    --host 0.0.0.0 \
    --port 5000 \
    --expose-prometheus /metrics