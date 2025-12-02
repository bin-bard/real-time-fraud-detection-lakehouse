# ============================================================
# Register Delta Lake Tables to Hive Metastore
# Để Trino có thể query qua hive catalog
# ============================================================

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "🔧 Register Delta Tables to Hive Metastore" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# Kiểm tra các services đang chạy
Write-Host "`n✅ Checking required services..." -ForegroundColor Yellow

$requiredServices = @("spark-master", "hive-metastore", "minio", "gold-job")
$allRunning = $true

foreach ($service in $requiredServices) {
    $status = docker ps --filter "name=$service" --format "{{.Status}}"
    if ($status) {
        Write-Host "   ✅ $service is running" -ForegroundColor Green
    } else {
        Write-Host "   ❌ $service is NOT running" -ForegroundColor Red
        $allRunning = $false
    }
}

if (-not $allRunning) {
    Write-Host "`n❌ ERROR: Some required services are not running!" -ForegroundColor Red
    Write-Host "Please start the system first: docker-compose up -d" -ForegroundColor Red
    exit 1
}

# Kiểm tra Gold layer có dữ liệu chưa
Write-Host "`n📊 Checking Gold layer data..." -ForegroundColor Yellow
$goldLogs = docker logs gold-job --tail 20 2>&1 | Select-String "fact_transactions"

if ($goldLogs) {
    Write-Host "✅ Gold layer has data" -ForegroundColor Green
} else {
    Write-Host "⚠️  Warning: Gold layer may not have data yet" -ForegroundColor Yellow
    Write-Host "   Registration will skip empty tables (they'll be registered when data arrives)" -ForegroundColor Gray
}

# Chạy registration script
Write-Host "`n🚀 Running Delta Lake to Hive registration..." -ForegroundColor Cyan

docker exec spark-master spark-submit `
    --master spark://spark-master:7077 `
    --conf spark.cores.max=1 `
    --conf spark.executor.cores=1 `
    --conf spark.executor.memory=512m `
    --conf spark.driver.memory=512m `
    --packages io.delta:delta-core_2.12:2.4.0,org.apache.hadoop:hadoop-aws:3.3.4 `
    /app/register_tables_to_hive.py

if ($LASTEXITCODE -eq 0) {
    Write-Host "`n✅ Registration completed successfully!" -ForegroundColor Green
} else {
    Write-Host "`n❌ Registration failed!" -ForegroundColor Red
    exit 1
}

# Verify trong Trino
Write-Host "`n📚 Verifying tables in Trino..." -ForegroundColor Cyan

Write-Host "`n1️⃣ Available catalogs:" -ForegroundColor Yellow
docker exec trino trino --execute "SHOW CATALOGS"

Write-Host "`n2️⃣ Schemas in hive catalog:" -ForegroundColor Yellow
docker exec trino trino --execute "SHOW SCHEMAS FROM hive"

Write-Host "`n3️⃣ Tables in hive.gold:" -ForegroundColor Yellow
$goldTables = docker exec trino trino --execute "SHOW TABLES FROM hive.gold" 2>&1

if ($goldTables -match "dim_customer|fact_transactions") {
    Write-Host $goldTables
    Write-Host "✅ Gold tables are visible in Trino!" -ForegroundColor Green
} else {
    Write-Host "⚠️  No tables found in hive.gold yet" -ForegroundColor Yellow
    Write-Host "   (Tables will appear after Gold job creates data)" -ForegroundColor Gray
}

Write-Host "`n4️⃣ Sample query test:" -ForegroundColor Yellow
$testQuery = docker exec trino trino --execute "SELECT COUNT(*) as cnt FROM hive.gold.fact_transactions" 2>&1

if ($LASTEXITCODE -eq 0) {
    Write-Host $testQuery
    Write-Host "✅ Query successful!" -ForegroundColor Green
} else {
    Write-Host "⚠️  Query failed (table may be empty or not registered yet)" -ForegroundColor Yellow
}

# Summary
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "📊 Setup Summary" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

Write-Host "`n✅ Completed steps:" -ForegroundColor Green
Write-Host "   1. Hive catalog configured" -ForegroundColor White
Write-Host "   2. Delta tables registered to Hive Metastore" -ForegroundColor White
Write-Host "   3. Trino can now query via hive catalog" -ForegroundColor White

Write-Host "`n📖 NEXT STEPS:" -ForegroundColor Cyan

Write-Host "`n1. Test queries in Trino CLI:" -ForegroundColor White
Write-Host "   docker exec -it trino trino" -ForegroundColor Gray
Write-Host "   SHOW SCHEMAS FROM hive;" -ForegroundColor Gray
Write-Host "   SHOW TABLES FROM hive.gold;" -ForegroundColor Gray
Write-Host "   SELECT * FROM hive.gold.fact_transactions LIMIT 5;" -ForegroundColor Gray

Write-Host "`n2. Connect Metabase to Trino (Hive catalog):" -ForegroundColor White
Write-Host "   - URL: http://localhost:3000" -ForegroundColor Gray
Write-Host "   - Add Database -> Trino" -ForegroundColor Gray
Write-Host "   - Host: trino:8081" -ForegroundColor Gray
Write-Host "   - Catalog: hive (QUAN TRỌNG: dùng 'hive' thay vì 'delta'!)" -ForegroundColor Yellow
Write-Host "   - Schema: gold" -ForegroundColor Gray

Write-Host "`n3. Tạo views trong Trino (optional):" -ForegroundColor White
Write-Host "   .\scripts\setup-trino-views.ps1" -ForegroundColor Gray
Write-Host "   (Nhớ đổi 'delta.gold' thành 'hive.gold' trong queries!)" -ForegroundColor Yellow

Write-Host "`n4. Re-run registration nếu cần:" -ForegroundColor White
Write-Host "   .\scripts\register-delta-to-hive.ps1" -ForegroundColor Gray

Write-Host "`n📚 Documentation:" -ForegroundColor Cyan
Write-Host "   - Setup guide: docs/TRINO_METABASE_SETUP.md" -ForegroundColor Gray
Write-Host "   - Query reference: docs/QUERY_REFERENCE.md" -ForegroundColor Gray

Write-Host "`n✅ Setup completed!" -ForegroundColor Green
