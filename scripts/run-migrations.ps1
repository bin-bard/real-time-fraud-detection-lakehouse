# Run database migrations for fraud chatbot improvements
# Date: 2025-12-10

Write-Host "🔧 Running Database Migrations..." -ForegroundColor Cyan

# Migration 1: Fix fraud_predictions table
Write-Host "`n📊 Migration 1: Fix fraud_predictions table..." -ForegroundColor Yellow

$migration1 = Get-Content "database/migrations/001_fix_fraud_predictions.sql" -Raw
$migration1 | docker exec -i postgres psql -U postgres -d frauddb

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Migration 1 completed successfully" -ForegroundColor Green
} else {
    Write-Host "❌ Migration 1 failed" -ForegroundColor Red
    exit 1
}

# Migration 2: Add sql_query to chat_history
Write-Host "`n📊 Migration 2: Add sql_query to chat_history..." -ForegroundColor Yellow

$migration2 = Get-Content "database/migrations/002_add_sql_query_to_chat_history.sql" -Raw
$migration2 | docker exec -i postgres psql -U postgres -d frauddb

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Migration 2 completed successfully" -ForegroundColor Green
} else {
    Write-Host "❌ Migration 2 failed" -ForegroundColor Red
    exit 1
}

# Verify tables
Write-Host "`n🔍 Verifying tables..." -ForegroundColor Yellow
docker exec -i postgres psql -U postgres -d frauddb -c "
SELECT 
    'fraud_predictions' as table_name,
    COUNT(*) as row_count 
FROM fraud_predictions
UNION ALL
SELECT 
    'chat_history' as table_name,
    COUNT(*) as row_count 
FROM chat_history;
"

Write-Host "`n✅ All migrations completed!" -ForegroundColor Green
Write-Host "`n📝 Next steps:" -ForegroundColor Cyan
Write-Host "1. Rebuild chatbot: docker-compose up -d --build fraud-chatbot" -ForegroundColor White
Write-Host "2. Test chatbot at: http://localhost:8501" -ForegroundColor White
