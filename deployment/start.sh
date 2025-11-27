#!/bin/bash
set -e

# Install dependencies
pip install -q mlflow boto3 psycopg2-binary

# Export gunicorn binding configuration
export GUNICORN_CMD_ARGS="--bind=0.0.0.0:5000 --timeout=120 --workers=3 --access-logfile=- --error-logfile=-"

# Start MLflow server (will use env vars for backend and artifact store)
exec mlflow server \
    --host 0.0.0.0 \
    --port 5000 \
    --backend-store-uri "${MLFLOW_BACKEND_STORE_URI}" \
    --default-artifact-root "${MLFLOW_DEFAULT_ARTIFACT_ROOT}"
