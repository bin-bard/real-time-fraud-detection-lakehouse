# PowerShell script để cấu hình Debezium PostgreSQL connector
# Chạy sau khi tất cả services đã start

Write-Host "🔧 Setting up Debezium PostgreSQL Connector..." -ForegroundColor Cyan

# Wait for Debezium Connect to be ready
Write-Host "⏳ Waiting for Debezium Connect to start (30 seconds)..." -ForegroundColor Yellow
Start-Sleep -Seconds 30

# Connector configuration
$connectorConfig = @{
    name = "postgres-fraud-connector"
    config = @{
        "connector.class" = "io.debezium.connector.postgresql.PostgresConnector"
        "database.hostname" = "postgres"
        "database.port" = "5432"
        "database.user" = "postgres"
        "database.password" = "postgres"
        "database.dbname" = "frauddb"
        "database.server.name" = "postgres"
        "table.include.list" = "public.transactions"
        "plugin.name" = "pgoutput"
        "publication.autocreate.mode" = "filtered"
        "topic.prefix" = "postgres"
        "transforms" = "unwrap"
        "transforms.unwrap.type" = "io.debezium.transforms.ExtractNewRecordState"
        "transforms.unwrap.drop.tombstones" = "false"
        "key.converter" = "org.apache.kafka.connect.json.JsonConverter"
        "value.converter" = "org.apache.kafka.connect.json.JsonConverter"
        "key.converter.schemas.enable" = "false"
        "value.converter.schemas.enable" = "false"
    }
} | ConvertTo-Json -Depth 10

# Register connector
try {
    $response = Invoke-RestMethod -Uri "http://localhost:8083/connectors" `
        -Method Post `
        -ContentType "application/json" `
        -Body $connectorConfig
    
    Write-Host ""
    Write-Host "✅ Debezium connector registered successfully!" -ForegroundColor Green
    Write-Host ""
    Write-Host "📊 Connector details:" -ForegroundColor Cyan
    $response | ConvertTo-Json -Depth 5
    
} catch {
    Write-Host ""
    Write-Host "❌ Error registering connector:" -ForegroundColor Red
    Write-Host $_.Exception.Message
    exit 1
}

Write-Host ""
Write-Host "📋 Useful commands:" -ForegroundColor Cyan
Write-Host "   Check status: curl http://localhost:8083/connectors/postgres-fraud-connector/status" -ForegroundColor White
Write-Host "   List connectors: curl http://localhost:8083/connectors" -ForegroundColor White
Write-Host "   Delete connector: curl -X DELETE http://localhost:8083/connectors/postgres-fraud-connector" -ForegroundColor White
Write-Host ""
Write-Host "🎯 Kafka topic created: postgres.public.transactions" -ForegroundColor Green
