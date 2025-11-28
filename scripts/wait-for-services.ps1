# Wait for services to be ready
Write-Host "Waiting for services to start..." -ForegroundColor Yellow

# Wait for PostgreSQL
Write-Host "`nChecking PostgreSQL..." -ForegroundColor Cyan
$retries = 0
$maxRetries = 30
while ($retries -lt $maxRetries) {
    $result = docker exec postgres psql -U postgres -c "\l" 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✓ PostgreSQL is ready" -ForegroundColor Green
        break
    }
    $retries++
    Write-Host "Waiting for PostgreSQL... ($retries/$maxRetries)" -ForegroundColor Gray
    Start-Sleep -Seconds 2
}

# Wait for database creation
Write-Host "`nChecking Sparkov database..." -ForegroundColor Cyan
$retries = 0
while ($retries -lt $maxRetries) {
    $result = docker exec postgres psql -U postgres -d sparkov -c "SELECT 1" 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✓ Sparkov database exists" -ForegroundColor Green
        break
    }
    $retries++
    Write-Host "Waiting for database creation... ($retries/$maxRetries)" -ForegroundColor Gray
    Start-Sleep -Seconds 3
}

# Check data load
Write-Host "`nChecking data load..." -ForegroundColor Cyan
$retries = 0
while ($retries -lt $maxRetries) {
    $count = docker exec postgres psql -U postgres -d sparkov -t -c "SELECT COUNT(*) FROM transactions;" 2>&1
    if ($LASTEXITCODE -eq 0 -and $count -match '\d+' -and [int]$count.Trim() -gt 0) {
        Write-Host "✓ Data loaded: $($count.Trim()) records" -ForegroundColor Green
        break
    }
    $retries++
    Write-Host "Waiting for data load... ($retries/$maxRetries)" -ForegroundColor Gray
    Start-Sleep -Seconds 5
}

# Wait for Kafka
Write-Host "`nChecking Kafka..." -ForegroundColor Cyan
$retries = 0
while ($retries -lt $maxRetries) {
    $result = docker exec kafka kafka-topics --bootstrap-server localhost:9092 --list 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✓ Kafka is ready" -ForegroundColor Green
        break
    }
    $retries++
    Write-Host "Waiting for Kafka... ($retries/$maxRetries)" -ForegroundColor Gray
    Start-Sleep -Seconds 2
}

# Wait for Debezium
Write-Host "`nChecking Debezium..." -ForegroundColor Cyan
$retries = 0
while ($retries -lt $maxRetries) {
    $result = docker exec debezium curl -s http://localhost:8083/ 2>&1
    if ($LASTEXITCODE -eq 0 -and $result -match "version") {
        Write-Host "✓ Debezium Connect is ready" -ForegroundColor Green
        break
    }
    $retries++
    Write-Host "Waiting for Debezium Connect... ($retries/$maxRetries)" -ForegroundColor Gray
    Start-Sleep -Seconds 2
}

# Check if connector exists
Write-Host "`nChecking Debezium connector..." -ForegroundColor Cyan
$connectors = docker exec debezium curl -s http://localhost:8083/connectors | ConvertFrom-Json
if ($connectors.Count -eq 0) {
    Write-Host "⚠ No connector found. Creating connector..." -ForegroundColor Yellow
    
    $connectorConfig = @"
{
  "name": "postgres-connector",
  "config": {
    "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
    "database.hostname": "postgres",
    "database.port": "5432",
    "database.user": "postgres",
    "database.password": "postgres",
    "database.dbname": "sparkov",
    "database.server.name": "postgres",
    "table.include.list": "public.transactions",
    "plugin.name": "pgoutput",
    "publication.autocreate.mode": "filtered",
    "slot.name": "debezium_slot"
  }
}
"@
    
    $result = docker exec debezium curl -s -X POST -H "Content-Type: application/json" --data $connectorConfig http://localhost:8083/connectors
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✓ Connector created successfully" -ForegroundColor Green
    } else {
        Write-Host "✗ Failed to create connector" -ForegroundColor Red
        exit 1
    }
    
    # Wait for connector to be ready
    Start-Sleep -Seconds 10
} else {
    Write-Host "✓ Connector already exists: $connectors" -ForegroundColor Green
}

# Check Kafka topic
Write-Host "`nChecking Kafka topic..." -ForegroundColor Cyan
$retries = 0
while ($retries -lt $maxRetries) {
    $topics = docker exec kafka kafka-topics --bootstrap-server localhost:9092 --list
    if ($topics -match "postgres.public.transactions") {
        Write-Host "✓ Topic 'postgres.public.transactions' exists" -ForegroundColor Green
        
        # Check message count
        $count = docker exec kafka kafka-run-class kafka.tools.GetOffsetShell --broker-list localhost:9092 --topic postgres.public.transactions --time -1 2>&1 | Select-String ":(\d+)$" | ForEach-Object { $_.Matches.Groups[1].Value } | Measure-Object -Sum
        Write-Host "  Messages in topic: $($count.Sum)" -ForegroundColor Cyan
        break
    }
    $retries++
    Write-Host "Waiting for Kafka topic... ($retries/$maxRetries)" -ForegroundColor Gray
    Start-Sleep -Seconds 3
}

Write-Host "`n✅ All services are ready!" -ForegroundColor Green
Write-Host "`nYou can now run the streaming job:" -ForegroundColor Yellow
Write-Host "docker exec spark-master /opt/spark/bin/spark-submit --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0,io.delta:delta-core_2.12:2.4.0,org.apache.hadoop:hadoop-aws:3.3.4 --conf `"spark.sql.extensions=io.delta.sql.DeltaSparkSessionExtension`" --conf `"spark.sql.catalog.spark_catalog=org.apache.spark.sql.delta.catalog.DeltaCatalog`" /app/streaming_job.py" -ForegroundColor White
