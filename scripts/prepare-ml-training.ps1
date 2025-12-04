# Prepare system for ML training by stopping non-essential services
# This frees up CPU and memory for Spark training jobs

Write-Host "🛑 Stopping non-essential services for ML training..." -ForegroundColor Yellow

# Stop query/dashboard services (not needed during training)
docker compose stop trino
docker compose stop metabase
docker compose stop hive-metastore

# Stop CDC pipeline (pause data ingestion)
docker compose stop data-producer
docker compose stop debezium

Write-Host "" -ForegroundColor Green
Write-Host "✅ Services stopped. Available for training:" -ForegroundColor Green
Write-Host "   - Spark (master + worker)" -ForegroundColor Cyan
Write-Host "   - MLflow" -ForegroundColor Cyan
Write-Host "   - MinIO" -ForegroundColor Cyan
Write-Host "   - PostgreSQL" -ForegroundColor Cyan
Write-Host "   - Airflow" -ForegroundColor Cyan
Write-Host "" -ForegroundColor Green
Write-Host "📊 Resource savings:" -ForegroundColor Green
Write-Host "   - ~2GB RAM freed" -ForegroundColor Cyan
Write-Host "   - ~1-2 CPU cores freed" -ForegroundColor Cyan
Write-Host "" -ForegroundColor Green
Write-Host "🚀 Ready to run ML training DAG!" -ForegroundColor Green
Write-Host "" -ForegroundColor Green
Write-Host "To restart services after training:" -ForegroundColor Yellow
Write-Host "   docker compose up -d" -ForegroundColor White
