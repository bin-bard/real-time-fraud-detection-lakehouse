# Restore all services after ML training completes

Write-Host "🔄 Restoring all services..." -ForegroundColor Yellow

docker compose up -d

Write-Host "" -ForegroundColor Green
Write-Host "✅ All services restored!" -ForegroundColor Green
Write-Host "" -ForegroundColor Green
Write-Host "📊 Running services:" -ForegroundColor Green
Write-Host "   - Real-time pipeline: Bronze streaming, Data producer, Debezium CDC" -ForegroundColor Cyan
Write-Host "   - Query engines: Trino, Hive Metastore" -ForegroundColor Cyan
Write-Host "   - Dashboards: Metabase" -ForegroundColor Cyan
Write-Host "   - ML: MLflow, Spark" -ForegroundColor Cyan
Write-Host "   - Storage: MinIO, PostgreSQL" -ForegroundColor Cyan
