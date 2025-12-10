# Script để xóa Docker images và volumes không dùng (AN TOÀN)
# ⚠️ CHỈ XÓA NHỮNG GÌ KHÔNG LIÊN QUAN ĐẾN DỰ ÁN HIỆN TẠI

Write-Host "🧹 Docker Cleanup Script - AN TOÀN cho dự án Real-Time Fraud Detection" -ForegroundColor Cyan
Write-Host "=" * 80

# Danh sách images CẦN GIỮ (từ docker-compose.yml)
$KEEP_IMAGES = @(
    "fraud-detection-api",
    "real-time-fraud-detection-lakehouse-fraud-chatbot",
    "real-time-fraud-detection-lakehouse-data-producer",
    "real-time-fraud-detection-lakehouse-hive-metastore",
    "custom-airflow",
    "real-time-fraud-detection-lakehouse-minio-setup",
    "custom-spark",
    "real-time-fraud-detection-lakehouse-bronze-streaming",
    "metabase/metabase",
    "postgres",
    "curlimages/curl",
    "python",
    "trinodb/trino",
    "minio/minio",
    "apache/airflow",
    "debezium/connect",
    "provectuslabs/kafka-ui",
    "confluentinc/cp-kafka",
    "confluentinc/cp-zookeeper",
    "apache/hive"
)

# Danh sách volumes CẦN GIỮ (từ docker-compose.yml)
$KEEP_VOLUMES = @(
    "real-time-fraud-detection-lakehouse_airflow_db",
    "real-time-fraud-detection-lakehouse_bronze_ivy_cache",
    "real-time-fraud-detection-lakehouse_metabase_db",
    "real-time-fraud-detection-lakehouse_metastore_db",
    "real-time-fraud-detection-lakehouse_minio_data",
    "real-time-fraud-detection-lakehouse_mlflow_db",
    "real-time-fraud-detection-lakehouse_postgres_data"
)

Write-Host "`n📋 Step 1: Kiểm tra images không dùng..." -ForegroundColor Yellow

# Lấy tất cả images
$all_images = docker images --format "{{.Repository}}:{{.Tag}}"

$unused_images = @()
foreach ($img in $all_images) {
    $is_keep = $false
    foreach ($keep in $KEEP_IMAGES) {
        if ($img -like "*$keep*") {
            $is_keep = $true
            break
        }
    }
    
    if (-not $is_keep -and $img -ne "<none>:<none>") {
        $unused_images += $img
    }
}

if ($unused_images.Count -gt 0) {
    Write-Host "`n🗑️  Tìm thấy $($unused_images.Count) images KHÔNG dùng:" -ForegroundColor Red
    $unused_images | ForEach-Object { Write-Host "   - $_" -ForegroundColor Gray }
    
    $confirm = Read-Host "`nBạn có muốn XÓA các images này? (y/N)"
    if ($confirm -eq 'y' -or $confirm -eq 'Y') {
        foreach ($img in $unused_images) {
            Write-Host "Deleting $img..." -ForegroundColor Yellow
            docker rmi $img 2>$null
        }
        Write-Host "✅ Đã xóa images không dùng" -ForegroundColor Green
    } else {
        Write-Host "⏭️  Bỏ qua xóa images" -ForegroundColor Cyan
    }
} else {
    Write-Host "✅ Không có images không dùng" -ForegroundColor Green
}

Write-Host "`n📋 Step 2: Kiểm tra volumes không dùng..." -ForegroundColor Yellow

# Lấy tất cả volumes
$all_volumes = docker volume ls --format "{{.Name}}"

$unused_volumes = @()
foreach ($vol in $all_volumes) {
    $is_keep = $false
    
    # Kiểm tra volumes trong KEEP_VOLUMES
    foreach ($keep in $KEEP_VOLUMES) {
        if ($vol -eq $keep) {
            $is_keep = $true
            break
        }
    }
    
    # Bỏ qua volumes của dự án khác (banking-data-pipeline, sqlserver)
    if ($vol -like "banking-data-pipeline*" -or $vol -like "sqlserver*") {
        $is_keep = $true
    }
    
    # Volumes có hash (UUID) - có thể là dangling
    if ($vol -match '^[a-f0-9]{64}$') {
        # Đây là dangling volume, KHÔNG giữ
        $is_keep = $false
    }
    
    if (-not $is_keep) {
        $unused_volumes += $vol
    }
}

if ($unused_volumes.Count -gt 0) {
    Write-Host "`n🗑️  Tìm thấy $($unused_volumes.Count) volumes KHÔNG dùng:" -ForegroundColor Red
    $unused_volumes | ForEach-Object { Write-Host "   - $_" -ForegroundColor Gray }
    
    $confirm = Read-Host "`nBạn có muốn XÓA các volumes này? (y/N)"
    if ($confirm -eq 'y' -or $confirm -eq 'Y') {
        foreach ($vol in $unused_volumes) {
            Write-Host "Deleting $vol..." -ForegroundColor Yellow
            docker volume rm $vol 2>$null
        }
        Write-Host "✅ Đã xóa volumes không dùng" -ForegroundColor Green
    } else {
        Write-Host "⏭️  Bỏ qua xóa volumes" -ForegroundColor Cyan
    }
} else {
    Write-Host "✅ Không có volumes không dùng" -ForegroundColor Green
}

Write-Host "`n📋 Step 3: Xóa dangling images (<none>)..." -ForegroundColor Yellow
$dangling = docker images -f "dangling=true" -q
if ($dangling) {
    docker rmi $dangling 2>$null
    Write-Host "✅ Đã xóa dangling images" -ForegroundColor Green
} else {
    Write-Host "✅ Không có dangling images" -ForegroundColor Green
}

Write-Host "`n📋 Step 4: Docker system prune (containers/networks stopped)..." -ForegroundColor Yellow
docker system prune -f

Write-Host "`n" + ("=" * 80)
Write-Host "🎉 Cleanup hoàn tất! Kiểm tra dung lượng:" -ForegroundColor Green
docker system df

Write-Host "`n💡 Lưu ý:" -ForegroundColor Cyan
Write-Host "   - Đã GIỮ LẠI tất cả images/volumes của dự án hiện tại" -ForegroundColor White
Write-Host "   - Đã GIỮ LẠI volumes của banking-data-pipeline và sqlserver" -ForegroundColor White
Write-Host "   - Chỉ xóa những gì KHÔNG liên quan đến các dự án đang chạy" -ForegroundColor White
