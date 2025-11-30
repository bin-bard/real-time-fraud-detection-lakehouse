#!/usr/bin/env pwsh
# Script tự động khởi động 3 streaming jobs song song

Write-Host "🚀 Starting Real-Time Fraud Detection Streaming Pipeline..." -ForegroundColor Cyan
Write-Host ""

# Function to start job in background
function Start-StreamingJob {
    param(
        [string]$JobName,
        [string]$ScriptPath,
        [string]$Packages
    )
    
    Write-Host "▶️  Starting $JobName..." -ForegroundColor Yellow
    
    $command = "docker exec spark-master /opt/spark/bin/spark-submit " +
               "--packages $Packages " +
               "--conf 'spark.sql.extensions=io.delta.sql.DeltaSparkSessionExtension' " +
               "--conf 'spark.sql.catalog.spark_catalog=org.apache.spark.sql.delta.catalog.DeltaCatalog' " +
               "$ScriptPath"
    
    # Start job in new PowerShell window
    Start-Process powershell -ArgumentList "-NoExit", "-Command", $command -WindowStyle Normal
    
    Write-Host "✅ $JobName started in new window" -ForegroundColor Green
    Start-Sleep -Seconds 2
}

# 1. Start Bronze Layer (Kafka → Delta Lake)
Write-Host ""
Write-Host "=" -NoNewline -ForegroundColor Cyan
Write-Host " BRONZE LAYER " -NoNewline -ForegroundColor White
Write-Host "=" -ForegroundColor Cyan
Start-StreamingJob -JobName "Bronze Layer" `
    -ScriptPath "/app/streaming_job.py" `
    -Packages "org.apache.spark:spark-sql-kafka-0-10_2.12:3.4.1,io.delta:delta-core_2.12:2.4.0,org.apache.hadoop:hadoop-aws:3.3.4"

Write-Host "⏳ Waiting 30 seconds for Bronze to initialize..." -ForegroundColor Yellow
Start-Sleep -Seconds 30

# 2. Start Silver Layer (Bronze → Features)
Write-Host ""
Write-Host "=" -NoNewline -ForegroundColor Cyan
Write-Host " SILVER LAYER " -NoNewline -ForegroundColor White
Write-Host "=" -ForegroundColor Cyan
Start-StreamingJob -JobName "Silver Layer" `
    -ScriptPath "/app/silver_layer_job.py" `
    -Packages "io.delta:delta-core_2.12:2.4.0,org.apache.hadoop:hadoop-aws:3.3.4"

Write-Host "⏳ Waiting 30 seconds for Silver to initialize..." -ForegroundColor Yellow
Start-Sleep -Seconds 30

# 3. Start Gold Layer (Silver → Star Schema)
Write-Host ""
Write-Host "=" -NoNewline -ForegroundColor Cyan
Write-Host " GOLD LAYER " -NoNewline -ForegroundColor White
Write-Host "=" -ForegroundColor Cyan
Start-StreamingJob -JobName "Gold Layer" `
    -ScriptPath "/app/gold_layer_dimfact_job.py" `
    -Packages "io.delta:delta-core_2.12:2.4.0,org.apache.hadoop:hadoop-aws:3.3.4"

Write-Host ""
Write-Host "=" -repeat 60 -ForegroundColor Cyan
Write-Host "🎉 All streaming jobs started successfully!" -ForegroundColor Green
Write-Host ""
Write-Host "📊 Monitor jobs:" -ForegroundColor Yellow
Write-Host "   - Spark UI: http://localhost:8080" -ForegroundColor White
Write-Host "   - MinIO: http://localhost:9001 (minio/minio123)" -ForegroundColor White
Write-Host "   - Kafka UI: http://localhost:9002" -ForegroundColor White
Write-Host ""
Write-Host "⚠️  To stop all jobs: Close all PowerShell windows or press Ctrl+C in each" -ForegroundColor Yellow
Write-Host "=" -repeat 60 -ForegroundColor Cyan
