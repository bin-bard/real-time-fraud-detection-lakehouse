# Build và Deploy Fraud Chatbot với cấu trúc mới
# Date: 2025-12-10

param(
    [switch]$SkipMigrations = $false,
    [switch]$CleanBuild = $false
)

Write-Host "🚀 Deploying Fraud Chatbot (New Structure)" -ForegroundColor Cyan
Write-Host "============================================`n" -ForegroundColor Cyan

# Check if docker is running
$dockerStatus = docker info 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Docker is not running! Please start Docker Desktop." -ForegroundColor Red
    exit 1
}

# Step 1: Run migrations (unless skipped)
if (-not $SkipMigrations) {
    Write-Host "📊 Step 1: Running database migrations..." -ForegroundColor Yellow
    & .\scripts\run-migrations.ps1
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Migrations failed! Aborting deployment." -ForegroundColor Red
        exit 1
    }
    Write-Host ""
}

# Step 2: Stop old chatbot
Write-Host "⏸️  Step 2: Stopping old chatbot..." -ForegroundColor Yellow
docker-compose stop fraud-chatbot
docker-compose rm -f fraud-chatbot

# Step 3: Clean build if requested
if ($CleanBuild) {
    Write-Host "🧹 Step 3: Clean build (removing old images)..." -ForegroundColor Yellow
    docker rmi real-time-fraud-detection-lakehouse-fraud-chatbot -f
}

# Step 4: Build new image
Write-Host "🔨 Step 4: Building new chatbot image..." -ForegroundColor Yellow
docker-compose build fraud-chatbot

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Build failed!" -ForegroundColor Red
    exit 1
}

# Step 5: Start chatbot
Write-Host "▶️  Step 5: Starting chatbot..." -ForegroundColor Yellow
docker-compose up -d fraud-chatbot

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Start failed!" -ForegroundColor Red
    exit 1
}

# Step 6: Wait for health check
Write-Host "⏳ Step 6: Waiting for chatbot to be healthy..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

$maxRetries = 12
$retryCount = 0
$healthy = $false

while ($retryCount -lt $maxRetries) {
    $retryCount++
    Write-Host "  Checking health... ($retryCount/$maxRetries)" -ForegroundColor Gray
    
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:8501/_stcore/health" -TimeoutSec 5 -UseBasicParsing
        if ($response.StatusCode -eq 200) {
            $healthy = $true
            break
        }
    } catch {
        # Continue waiting
    }
    
    Start-Sleep -Seconds 5
}

Write-Host ""

if ($healthy) {
    Write-Host "✅ Chatbot deployed successfully!" -ForegroundColor Green
    Write-Host ""
    Write-Host "📋 Service Info:" -ForegroundColor Cyan
    Write-Host "  - Chatbot UI: http://localhost:8501" -ForegroundColor White
    Write-Host "  - Container: fraud-chatbot" -ForegroundColor White
    Write-Host ""
    Write-Host "📝 Quick Commands:" -ForegroundColor Cyan
    Write-Host "  - View logs:    docker logs fraud-chatbot -f" -ForegroundColor White
    Write-Host "  - Restart:      docker-compose restart fraud-chatbot" -ForegroundColor White
    Write-Host "  - Stop:         docker-compose stop fraud-chatbot" -ForegroundColor White
    Write-Host ""
    Write-Host "🎯 Test Agent Features:" -ForegroundColor Cyan
    Write-Host "  1. SQL Analytics: 'Top 5 bang có fraud rate cao nhất'" -ForegroundColor White
    Write-Host "  2. Prediction: 'Dự đoán giao dịch `$850 lúc 2h sáng'" -ForegroundColor White
    Write-Host "  3. Complex: 'Check `$500 và so sánh fraud rate TX'" -ForegroundColor White
    Write-Host "  4. Manual Form: Sidebar > Tools > Manual Prediction" -ForegroundColor White
    Write-Host "  5. Batch Upload: Sidebar > Tools > Batch Upload" -ForegroundColor White
    Write-Host ""
} else {
    Write-Host "⚠️  Chatbot started but health check failed" -ForegroundColor Yellow
    Write-Host "   Check logs with: docker logs fraud-chatbot" -ForegroundColor White
}
