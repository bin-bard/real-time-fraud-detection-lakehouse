# ============================================================
# TEST SCRIPT - Chatbot Architecture Improvements
# ============================================================
# Tests:
# 1. Schema Caching (TTL-based)
# 2. Dynamic Schema Loading (all 14 tables/views)
# 3. Config-based Prompts & Business Rules
# 4. API Feature Engineering (/predict/raw endpoint)
# ============================================================

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "🧪 TESTING CHATBOT IMPROVEMENTS" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# Test 1: Check if services are running
Write-Host "`n📋 TEST 1: Service Health Check" -ForegroundColor Yellow
Write-Host "Checking if fraud-chatbot and fraud-detection-api are running..."

$chatbotRunning = docker ps --filter "name=fraud-chatbot" --filter "status=running" -q
$apiRunning = docker ps --filter "name=fraud-detection-api" --filter "status=running" -q

if (-not $chatbotRunning) {
    Write-Host "❌ fraud-chatbot is not running!" -ForegroundColor Red
    Write-Host "Run: docker compose up -d --build fraud-chatbot" -ForegroundColor Yellow
    exit 1
}

if (-not $apiRunning) {
    Write-Host "❌ fraud-detection-api is not running!" -ForegroundColor Red
    Write-Host "Run: docker compose up -d --build fraud-detection-api" -ForegroundColor Yellow
    exit 1
}

Write-Host "✅ Both services are running" -ForegroundColor Green

# Test 2: Test API /predict/raw endpoint (Feature Engineering)
Write-Host "`n📋 TEST 2: API Feature Engineering (/predict/raw)" -ForegroundColor Yellow
Write-Host "Testing new endpoint that accepts raw transaction data..."

$rawPayload = @{
    amt = 150.50
    trans_hour = 23
    distance_from_last_km = 250.0
} | ConvertTo-Json

try {
    $response = Invoke-RestMethod -Uri "http://localhost:8001/predict/raw" `
        -Method POST `
        -Body $rawPayload `
        -ContentType "application/json"
    
    Write-Host "✅ API Response:" -ForegroundColor Green
    Write-Host "   Fraud Probability: $($response.fraud_probability)" -ForegroundColor White
    Write-Host "   Risk Level: $($response.risk_level)" -ForegroundColor White
    Write-Host "   Engineered Features: $($response.engineered_features.Keys -join ', ')" -ForegroundColor White
    
    # Verify features were computed
    if ($response.engineered_features.log_amount -and 
        $response.engineered_features.hour_sin -and 
        $response.engineered_features.hour_cos) {
        Write-Host "✅ Feature engineering working correctly" -ForegroundColor Green
    } else {
        Write-Host "❌ Feature engineering incomplete!" -ForegroundColor Red
    }
} catch {
    Write-Host "❌ API call failed: $_" -ForegroundColor Red
}

# Test 3: Check Schema Loader Cache Logs
Write-Host "`n📋 TEST 3: Schema Caching (Cache HIT/MISS)" -ForegroundColor Yellow
Write-Host "Checking cache behavior in logs..."

# Clear previous logs to see fresh cache activity
Write-Host "Restarting chatbot to test cache from scratch..."
docker compose restart fraud-chatbot | Out-Null
Start-Sleep -Seconds 5

# Trigger schema load by checking chatbot logs
Write-Host "Waiting for chatbot to initialize..."
Start-Sleep -Seconds 3

$logs = docker logs fraud-chatbot --tail 100 2>&1 | Out-String

# Check for cache initialization
if ($logs -match "Schema loader initialized with cache TTL: (\d+)s") {
    Write-Host "✅ Cache initialized with TTL: $($Matches[1]) seconds" -ForegroundColor Green
} else {
    Write-Host "⚠️  Cache initialization not found in logs" -ForegroundColor Yellow
}

# Check for cache misses (first load)
$cacheMisses = ($logs | Select-String -Pattern "Cache MISS" -AllMatches).Matches.Count
if ($cacheMisses -gt 0) {
    Write-Host "✅ Cache MISS detected ($cacheMisses times) - Normal on first load" -ForegroundColor Green
} else {
    Write-Host "⚠️  No cache MISS found - might be using old cache" -ForegroundColor Yellow
}

# Test 4: Verify All 14 Tables/Views are Loaded
Write-Host "`n📋 TEST 4: Dynamic Schema Loading (14 Tables/Views)" -ForegroundColor Yellow
Write-Host "Checking if all tables are loaded from Trino..."

$expectedTables = @(
    # 9 Views
    "state_summary",
    "merchant_analysis",
    "category_summary",
    "amount_summary",
    "hourly_summary",
    "daily_summary",
    "latest_metrics",
    "fraud_patterns",
    "time_period_analysis",
    # 5 Base Tables
    "fact_transactions",
    "dim_customer",
    "dim_merchant",
    "dim_time",
    "dim_location"
)

Write-Host "Expected tables/views: $($expectedTables.Count)" -ForegroundColor White

# Query Trino to verify
try {
    docker exec -it trino trino --execute "SHOW TABLES FROM delta.gold" > tables.txt 2>&1
    $trinoTables = Get-Content tables.txt | Select-String -Pattern "^\s*\w+" | ForEach-Object { $_.ToString().Trim() }
    Remove-Item tables.txt -ErrorAction SilentlyContinue
    
    $foundCount = 0
    $missingTables = @()
    
    foreach ($table in $expectedTables) {
        if ($trinoTables -contains $table) {
            $foundCount++
        } else {
            $missingTables += $table
        }
    }
    
    Write-Host "✅ Found: $foundCount / $($expectedTables.Count) tables" -ForegroundColor Green
    
    if ($missingTables.Count -gt 0) {
        Write-Host "⚠️  Missing tables: $($missingTables -join ', ')" -ForegroundColor Yellow
        Write-Host "   Run: docker exec -it trino trino" -ForegroundColor Yellow
        Write-Host "   Then execute SQL from: sql/gold_layer_views_delta.sql" -ForegroundColor Yellow
    }
} catch {
    Write-Host "⚠️  Could not query Trino: $_" -ForegroundColor Yellow
}

# Test 5: Verify Config Files Exist
Write-Host "`n📋 TEST 5: Configuration Files (YAML)" -ForegroundColor Yellow

$promptsConfig = "services\fraud-chatbot\config\prompts.yaml"
$rulesConfig = "services\fraud-chatbot\config\business_rules.yaml"

if (Test-Path $promptsConfig) {
    Write-Host "✅ prompts.yaml exists" -ForegroundColor Green
    $promptsContent = Get-Content $promptsConfig -Raw
    if ($promptsContent -match "system_prompt:" -and $promptsContent -match "{database_schema}") {
        Write-Host "   Contains system_prompt with {database_schema} placeholder" -ForegroundColor White
    }
} else {
    Write-Host "❌ prompts.yaml NOT FOUND!" -ForegroundColor Red
}

if (Test-Path $rulesConfig) {
    Write-Host "✅ business_rules.yaml exists" -ForegroundColor Green
    $rulesContent = Get-Content $rulesConfig -Raw
    if ($rulesContent -match "risk_thresholds:" -and $rulesContent -match "alert_threshold_amount:") {
        Write-Host "   Contains risk_thresholds and alert_threshold_amount" -ForegroundColor White
    }
} else {
    Write-Host "❌ business_rules.yaml NOT FOUND!" -ForegroundColor Red
}

# Test 6: Test Chatbot Query (Integration Test)
Write-Host "`n📋 TEST 6: Chatbot Integration Test" -ForegroundColor Yellow
Write-Host "Testing chatbot query with schema caching..."

$chatPayload = @{
    message = "Show me the latest fraud metrics"
} | ConvertTo-Json

try {
    Write-Host "Sending query to chatbot..." -ForegroundColor White
    $chatResponse = Invoke-RestMethod -Uri "http://localhost:8003/chat" `
        -Method POST `
        -Body $chatPayload `
        -ContentType "application/json" `
        -TimeoutSec 30
    
    Write-Host "✅ Chatbot Response:" -ForegroundColor Green
    Write-Host $chatResponse.response -ForegroundColor White
    
    # Check logs for cache HIT (should hit cache on 2nd query)
    Start-Sleep -Seconds 2
    $newLogs = docker logs fraud-chatbot --tail 50 2>&1 | Out-String
    $cacheHits = ($newLogs | Select-String -Pattern "Cache HIT" -AllMatches).Matches.Count
    
    if ($cacheHits -gt 0) {
        Write-Host "✅ Cache HIT detected ($cacheHits times) - Schema caching working!" -ForegroundColor Green
    } else {
        Write-Host "⚠️  No cache HIT - Might be first query or cache expired" -ForegroundColor Yellow
    }
    
} catch {
    Write-Host "⚠️  Chatbot query failed: $_" -ForegroundColor Yellow
    Write-Host "   Check logs: docker logs fraud-chatbot --tail 50" -ForegroundColor Yellow
}

# Test 7: Cache Expiration Test (Optional - takes time)
Write-Host "`n📋 TEST 7: Cache Expiration (Optional)" -ForegroundColor Yellow
$testExpiration = Read-Host "Test cache expiration (5min wait)? (y/N)"

if ($testExpiration -eq 'y') {
    Write-Host "Waiting 5 minutes for cache to expire..."
    Start-Sleep -Seconds 300
    
    # Trigger another query
    try {
        Invoke-RestMethod -Uri "http://localhost:8003/chat" `
            -Method POST `
            -Body $chatPayload `
            -ContentType "application/json" | Out-Null
        
        Start-Sleep -Seconds 2
        $expiredLogs = docker logs fraud-chatbot --tail 30 2>&1 | Out-String
        
        if ($expiredLogs -match "Cache MISS") {
            Write-Host "✅ Cache expired and refreshed correctly" -ForegroundColor Green
        } else {
            Write-Host "⚠️  Cache might still be valid" -ForegroundColor Yellow
        }
    } catch {
        Write-Host "⚠️  Query failed: $_" -ForegroundColor Yellow
    }
} else {
    Write-Host "⏭️  Skipped cache expiration test" -ForegroundColor Gray
}

# Summary
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "📊 TEST SUMMARY" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

Write-Host "`n✅ Completed Tests:" -ForegroundColor Green
Write-Host "   1. Service health check" -ForegroundColor White
Write-Host "   2. API feature engineering (/predict/raw)" -ForegroundColor White
Write-Host "   3. Schema caching (cache HIT/MISS)" -ForegroundColor White
Write-Host "   4. Dynamic schema loading (14 tables/views)" -ForegroundColor White
Write-Host "   5. Configuration files (YAML)" -ForegroundColor White
Write-Host "   6. Chatbot integration test" -ForegroundColor White

Write-Host "`n📋 Manual Verification:" -ForegroundColor Yellow
Write-Host "   • Check full logs: docker logs fraud-chatbot" -ForegroundColor White
Write-Host "   • Query Trino: docker exec -it trino trino" -ForegroundColor White
Write-Host "   • Test with Postman/curl at http://localhost:8003/chat" -ForegroundColor White

Write-Host "`n🎯 Next Steps:" -ForegroundColor Cyan
Write-Host "   1. Implement alert_threshold_amount functionality" -ForegroundColor White
Write-Host "   2. Add cache warming on startup" -ForegroundColor White
Write-Host "   3. Add cache metrics endpoint" -ForegroundColor White
Write-Host "   4. Create views in Trino if missing" -ForegroundColor White

Write-Host "`n========================================" -ForegroundColor Cyan
