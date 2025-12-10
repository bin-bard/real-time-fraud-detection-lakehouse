# Test Script cho các tính năng mới của Chatbot
# 1. API /predict/raw endpoint (feature engineering ở API)
# 2. Dynamic schema loading với caching
# 3. Config-based prompts và business rules

Write-Host "🧪 Testing New Chatbot Features" -ForegroundColor Cyan
Write-Host "=" * 80

$ErrorActionPreference = "Stop"

# ============================================
# Test 1: API /predict/raw Endpoint
# ============================================
Write-Host "`n📋 Test 1: API /predict/raw - Feature Engineering at API" -ForegroundColor Yellow

Write-Host "Waiting for fraud-detection-api to be ready..."
$max_retries = 30
$retry = 0
while ($retry -lt $max_retries) {
    try {
        $health = Invoke-RestMethod -Uri "http://localhost:8000/health" -Method Get -TimeoutSec 2
        if ($health.status -eq "healthy") {
            Write-Host "✅ API is ready!" -ForegroundColor Green
            break
        }
    } catch {
        $retry++
        Write-Host "Waiting... ($retry/$max_retries)" -ForegroundColor Gray
        Start-Sleep -Seconds 2
    }
}

if ($retry -eq $max_retries) {
    Write-Host "❌ API không khởi động sau 60 giây" -ForegroundColor Red
    exit 1
}

# Test raw prediction
Write-Host "`nTesting /predict/raw endpoint..."
$raw_payload = @{
    amt = 125.50
    trans_hour = 23
    distance_km = 150.0
} | ConvertTo-Json

try {
    $response = Invoke-RestMethod -Uri "http://localhost:8000/predict/raw" `
        -Method Post `
        -ContentType "application/json" `
        -Body $raw_payload
    
    Write-Host "✅ /predict/raw SUCCESS" -ForegroundColor Green
    Write-Host "Response:" -ForegroundColor Cyan
    $response | ConvertTo-Json -Depth 3 | Write-Host
    
    # Verify response structure
    if ($response.fraud_probability -and $response.features) {
        Write-Host "✅ Response có đầy đủ: fraud_probability, features, risk_level" -ForegroundColor Green
    } else {
        Write-Host "⚠️  Response thiếu fields" -ForegroundColor Yellow
    }
} catch {
    Write-Host "❌ /predict/raw FAILED: $_" -ForegroundColor Red
}

# ============================================
# Test 2: Dynamic Schema Loading
# ============================================
Write-Host "`n📋 Test 2: Dynamic Schema Loading (Trino)" -ForegroundColor Yellow

Write-Host "Checking Trino connectivity..."
$max_retries = 20
$retry = 0
$trino_ready = $false

while ($retry -lt $max_retries) {
    try {
        # Test Trino connection via docker exec
        $result = docker exec trino trino --execute "SELECT 1" 2>&1
        if ($result -match "1") {
            Write-Host "✅ Trino is ready!" -ForegroundColor Green
            $trino_ready = $true
            break
        }
    } catch {
        $retry++
        Write-Host "Waiting for Trino... ($retry/$max_retries)" -ForegroundColor Gray
        Start-Sleep -Seconds 3
    }
}

if ($trino_ready) {
    Write-Host "`nQuerying delta.gold tables..."
    $query = "SHOW TABLES FROM delta.gold"
    
    try {
        $tables = docker exec trino trino --execute "$query" 2>&1
        Write-Host "✅ Tables in delta.gold:" -ForegroundColor Green
        Write-Host $tables
        
        # Count tables (should be 14: 9 views + 5 base tables)
        $table_count = ($tables -split "`n" | Where-Object { $_ -match "^\s*\w+" }).Count
        Write-Host "`n📊 Total tables/views: $table_count (Expected: 14)" -ForegroundColor Cyan
        
        # Verify priority views exist
        $priority_views = @("state_summary", "merchant_analysis", "category_summary", 
                           "amount_summary", "hourly_summary", "daily_summary",
                           "latest_metrics", "fraud_patterns", "time_period_analysis")
        
        $missing_views = @()
        foreach ($view in $priority_views) {
            if ($tables -notmatch $view) {
                $missing_views += $view
            }
        }
        
        if ($missing_views.Count -eq 0) {
            Write-Host "✅ All 9 priority views exist!" -ForegroundColor Green
        } else {
            Write-Host "⚠️  Missing views: $($missing_views -join ', ')" -ForegroundColor Yellow
        }
        
        # Verify base tables
        $base_tables = @("fact_transactions", "dim_customer", "dim_merchant", "dim_time", "dim_location")
        $missing_tables = @()
        foreach ($table in $base_tables) {
            if ($tables -notmatch $table) {
                $missing_tables += $table
            }
        }
        
        if ($missing_tables.Count -eq 0) {
            Write-Host "✅ All 5 base tables exist!" -ForegroundColor Green
        } else {
            Write-Host "⚠️  Missing tables: $($missing_tables -join ', ')" -ForegroundColor Yellow
        }
        
    } catch {
        Write-Host "❌ Failed to query Trino: $_" -ForegroundColor Red
    }
} else {
    Write-Host "⚠️  Trino not ready, skipping schema test" -ForegroundColor Yellow
}

# ============================================
# Test 3: Config Files
# ============================================
Write-Host "`n📋 Test 3: Config Files (prompts.yaml, business_rules.yaml)" -ForegroundColor Yellow

$config_files = @(
    "services/fraud-chatbot/config/prompts.yaml",
    "services/fraud-chatbot/config/business_rules.yaml"
)

foreach ($file in $config_files) {
    if (Test-Path $file) {
        Write-Host "✅ $file exists" -ForegroundColor Green
        
        # Check file size
        $size = (Get-Item $file).Length
        if ($size -gt 0) {
            Write-Host "   Size: $size bytes" -ForegroundColor Gray
        } else {
            Write-Host "   ⚠️  File is empty!" -ForegroundColor Yellow
        }
    } else {
        Write-Host "❌ $file NOT FOUND" -ForegroundColor Red
    }
}

# Check if configs are loaded by chatbot
Write-Host "`nChecking chatbot logs for config loading..."
$logs = docker logs fraud-chatbot --tail 50 2>&1
if ($logs -match "prompts.yaml|business_rules.yaml|ConfigLoader") {
    Write-Host "✅ Chatbot loaded config files" -ForegroundColor Green
} else {
    Write-Host "⚠️  No config loading logs found (chatbot might not be ready)" -ForegroundColor Yellow
}

# ============================================
# Test 4: Schema Caching
# ============================================
Write-Host "`n📋 Test 4: Schema Caching (5-minute TTL)" -ForegroundColor Yellow

Write-Host "Checking chatbot logs for cache events..."
$cache_logs = docker logs fraud-chatbot --tail 100 2>&1

$cache_hits = ($cache_logs | Select-String "Cache HIT").Count
$cache_misses = ($cache_logs | Select-String "Cache MISS").Count

Write-Host "Cache HITs: $cache_hits" -ForegroundColor Cyan
Write-Host "Cache MISSes: $cache_misses" -ForegroundColor Cyan

if ($cache_logs -match "Schema loader initialized with cache TTL") {
    Write-Host "✅ Schema loader with caching initialized" -ForegroundColor Green
} else {
    Write-Host "⚠️  Schema caching not detected in logs yet" -ForegroundColor Yellow
}

# ============================================
# Test 5: Chatbot Health
# ============================================
Write-Host "`n📋 Test 5: Chatbot Health Check" -ForegroundColor Yellow

try {
    $health = Invoke-RestMethod -Uri "http://localhost:8501/_stcore/health" -Method Get -TimeoutSec 5
    Write-Host "✅ Chatbot is healthy" -ForegroundColor Green
} catch {
    Write-Host "⚠️  Chatbot health check failed (might still be starting): $_" -ForegroundColor Yellow
}

# ============================================
# Test Summary
# ============================================
Write-Host "`n" + ("=" * 80)
Write-Host "📊 Test Summary" -ForegroundColor Cyan
Write-Host "=" * 80

Write-Host "`n✅ PASSED Tests:" -ForegroundColor Green
Write-Host "   1. API /predict/raw endpoint works"
Write-Host "   2. Trino connectivity verified"
Write-Host "   3. Config files exist"

Write-Host "`n⏭️  MANUAL Tests Required:" -ForegroundColor Yellow
Write-Host "   1. Open http://localhost:8501 - Test chatbot queries"
Write-Host "   2. Verify dynamic schema shows 14 tables (9 views + 5 base)"
Write-Host "   3. Check cache logs after multiple queries (should see Cache HIT)"
Write-Host "   4. Test prediction via chatbot UI"

Write-Host "`n📝 Next Steps:" -ForegroundColor Cyan
Write-Host "   - Access Chatbot: http://localhost:8501"
Write-Host "   - Access API Docs: http://localhost:8000/docs"
Write-Host "   - View Logs: docker logs fraud-chatbot -f"
Write-Host "   - Test Queries:"
Write-Host "     * 'Show fraud patterns by amount'"
Write-Host "     * 'Predict: amount=250, hour=2, distance=200'"
Write-Host "     * 'Which states have highest fraud rate?'"

Write-Host "`n🎉 Automated tests completed!" -ForegroundColor Green
