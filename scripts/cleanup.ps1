# Cleanup Docker containers, networks, volumes
# ⚠️ USE WITH CAUTION - Xóa tất cả volumes (mất dữ liệu)

Write-Host "🗑️ Stopping and removing all containers..." -ForegroundColor Yellow
docker-compose down -v --remove-orphans

Write-Host "`n🧹 Pruning unused Docker resources..." -ForegroundColor Yellow
docker system prune -f

Write-Host "`n✅ Cleanup completed!" -ForegroundColor Green
Write-Host "💡 To restart: docker-compose up -d" -ForegroundColor Cyan
