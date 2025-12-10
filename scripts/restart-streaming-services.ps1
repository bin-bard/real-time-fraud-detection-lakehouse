<#
.SYNOPSIS
Restart streaming services (Bronze + Alert) safely
Có thể chạy bất cứ lúc nào mà không bị lỗi duplicate/offset issues

.DESCRIPTION
- Stop streaming services
- Clear checkpoints (optional - chỉ khi muốn reprocess từ đầu)
- Restart services
- Services sẽ chỉ process NEW messages từ thời điểm restart (latest offset)

.PARAMETER ClearCheckpoints
Xóa checkpoints để reprocess toàn bộ data từ đầu (mặc định: false)
#>

param(
    [switch]$ClearCheckpoints = $false
)

$ErrorActionPreference = "Stop"

Write-Host "🔄 Restarting Streaming Services..." -ForegroundColor Cyan
Write-Host "=" * 80

# 1. Stop services
Write-Host "`n📛 Stopping streaming services..." -ForegroundColor Yellow
docker-compose stop spark-realtime-prediction

# 2. Clear checkpoints if requested
if ($ClearCheckpoints) {
    Write-Host "`n🗑️  Clearing checkpoints (will reprocess all data)..." -ForegroundColor Yellow
    
    # Clear Bronze checkpoint
    docker exec -it minio mc rm --recursive --force minio/lakehouse/checkpoints/bronze/ 2>$null
    Write-Host "  ✅ Bronze checkpoint cleared" -ForegroundColor Green
    
    # Clear Alert checkpoint
    docker exec -it minio mc rm --recursive --force minio/lakehouse/checkpoints/realtime-prediction/ 2>$null
    Write-Host "  ✅ Alert checkpoint cleared" -ForegroundColor Green
    
    Write-Host "`n⚠️  WARNING: Services will reprocess ALL Kafka messages from beginning" -ForegroundColor Red
} else {
    Write-Host "`n✅ Keeping checkpoints (will resume from last offset)" -ForegroundColor Green
}

# 3. Restart services
Write-Host "`n🚀 Starting streaming services..." -ForegroundColor Yellow
docker-compose start spark-realtime-prediction

Start-Sleep -Seconds 5

# 4. Check status
Write-Host "`n📊 Service Status:" -ForegroundColor Cyan
docker-compose ps spark-realtime-prediction

Write-Host "`n✅ Services restarted successfully!" -ForegroundColor Green
Write-Host "`nℹ️  Monitor logs:" -ForegroundColor Cyan
Write-Host "  Alert:   docker logs -f spark-realtime-prediction" -ForegroundColor White

Write-Host "`n💡 Tips:" -ForegroundColor Yellow
Write-Host "  - Services use 'latest' offset → Only NEW messages after restart" -ForegroundColor White
Write-Host "  - To reprocess all data: .\restart-streaming-services.ps1 -ClearCheckpoints" -ForegroundColor White
Write-Host "  - Safe to stop/start anytime without duplicates" -ForegroundColor White
