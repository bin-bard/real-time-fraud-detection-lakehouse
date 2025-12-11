# Test Real-Time Fraud Detection Flow
# Insert test transactions → Debezium CDC → Kafka → Spark Structured Streaming → FastAPI → Slack

Write-Host "================================" -ForegroundColor Cyan
Write-Host "🚀 Testing Real-Time Fraud Detection Flow" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Check if services are running
Write-Host "📋 Step 1: Checking services status..." -ForegroundColor Yellow

$services = @(
    "postgres",
    "kafka",
    "fraud-detection-api",
    "spark-realtime-prediction"
)

foreach ($service in $services) {
    $status = docker ps --filter "name=$service" --format "{{.Status}}"
    if ($status) {
        Write-Host "  ✅ $service : $status" -ForegroundColor Green
    } else {
        Write-Host "  ❌ $service : NOT RUNNING" -ForegroundColor Red
        Write-Host ""
        Write-Host "❌ Error: Required services not running" -ForegroundColor Red
        Write-Host "Run: docker-compose up -d spark-realtime-prediction" -ForegroundColor Yellow
        exit 1
    }
}

Write-Host ""

# Step 2: Check Slack webhook configuration
Write-Host "📋 Step 2: Checking Slack webhook..." -ForegroundColor Yellow

$slackWebhook = docker exec spark-realtime-prediction printenv SLACK_WEBHOOK_URL 2>$null

if ($slackWebhook -and $slackWebhook -match "https://hooks.slack.com") {
    Write-Host "  ✅ Slack webhook configured" -ForegroundColor Green
    Write-Host "     URL: $($slackWebhook.Substring(0, 50))..." -ForegroundColor Gray
} else {
    Write-Host "  ⚠️  Slack webhook NOT configured" -ForegroundColor Yellow
    Write-Host "     Alerts will be logged but not sent to Slack" -ForegroundColor Gray
}

Write-Host ""

# Step 3: Check Kafka topic
Write-Host "📋 Step 3: Checking Kafka topic..." -ForegroundColor Yellow

$kafkaTopic = docker exec kafka kafka-topics --bootstrap-server localhost:9092 --list 2>$null | Select-String "postgres.public.transactions"

if ($kafkaTopic) {
    Write-Host "  ✅ Kafka topic exists: postgres.public.transactions" -ForegroundColor Green
} else {
    Write-Host "  ⚠️  Kafka topic not found (may be created on first message)" -ForegroundColor Yellow
}

Write-Host ""

# Step 4: Insert test transactions
Write-Host "📋 Step 4: Inserting test transactions..." -ForegroundColor Yellow
Write-Host "  Will insert 4 transactions (3 fraud + 1 normal)" -ForegroundColor Gray
Write-Host ""

$env:PGPASSWORD = "postgres"

docker exec postgres psql -U postgres -d frauddb -f /docker-entrypoint-initdb.d/test_realtime_flow.sql

if ($LASTEXITCODE -eq 0) {
    Write-Host "  ✅ Test transactions inserted successfully" -ForegroundColor Green
} else {
    Write-Host "  ❌ Failed to insert transactions" -ForegroundColor Red
    exit 1
}

Write-Host ""

# Step 5: Monitor streaming job logs
Write-Host "📋 Step 5: Monitoring streaming job (15 seconds)..." -ForegroundColor Yellow
Write-Host "  Watch for:" -ForegroundColor Gray
Write-Host "    - Batch processing messages" -ForegroundColor Gray
Write-Host "    - API predictions" -ForegroundColor Gray
Write-Host "    - Slack alerts sent" -ForegroundColor Gray
Write-Host ""

Write-Host "================================" -ForegroundColor Cyan
Start-Sleep -Seconds 2

docker logs spark-realtime-prediction --tail 50 --follow &

$job = Start-Job -ScriptBlock { 
    param($container)
    docker logs $container --tail 50 --follow
} -ArgumentList "spark-realtime-prediction"

Start-Sleep -Seconds 15
Stop-Job $job
Remove-Job $job

Write-Host ""
Write-Host "================================" -ForegroundColor Cyan

# Step 6: Verify predictions in database
Write-Host "📋 Step 6: Checking fraud_predictions table..." -ForegroundColor Yellow

$predictions = docker exec postgres psql -U postgres -d frauddb -c "
    SELECT 
        trans_num,
        prediction_score,
        is_fraud_predicted,
        model_version,
        prediction_time
    FROM fraud_predictions
    WHERE trans_num LIKE 'RT_%'
    ORDER BY prediction_time DESC
    LIMIT 10;
" 2>$null

if ($predictions) {
    Write-Host ""
    Write-Host $predictions
    Write-Host ""
    Write-Host "  ✅ Predictions saved to database" -ForegroundColor Green
} else {
    Write-Host "  ⚠️  No predictions found (check if streaming job is processing)" -ForegroundColor Yellow
}

Write-Host ""

# Step 7: Check Slack channel
Write-Host "📋 Step 7: Check Slack alerts..." -ForegroundColor Yellow
Write-Host ""

if ($slackWebhook -and $slackWebhook -match "https://hooks.slack.com") {
    Write-Host "  ✅ Check your Slack channel for 3 fraud alerts:" -ForegroundColor Green
    Write-Host "     - 🔴 HIGH RISK (large amount + distant)" -ForegroundColor Red
    Write-Host "     - 🟡 MEDIUM RISK (medium amount)" -ForegroundColor Yellow
    Write-Host "     - 🟢 LOW RISK (small amount)" -ForegroundColor Green
    Write-Host ""
    Write-Host "  📱 Open Slack to verify alerts were received" -ForegroundColor Cyan
} else {
    Write-Host "  ⚠️  Slack not configured - alerts logged only" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "================================" -ForegroundColor Cyan
Write-Host "✅ Test completed!" -ForegroundColor Green
Write-Host "================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "📊 Summary:" -ForegroundColor Cyan
Write-Host "  - Inserted: 4 test transactions (3 fraud, 1 normal)" -ForegroundColor White
Write-Host "  - Expected: 3 Slack alerts (ALL fraud levels)" -ForegroundColor White
Write-Host "  - Policy: Alert on ALL fraud detections, not just HIGH" -ForegroundColor White
Write-Host ""

Write-Host "🔍 Useful commands:" -ForegroundColor Cyan
Write-Host "  - View logs: docker logs spark-realtime-prediction -f" -ForegroundColor Gray
Write-Host "  - Check predictions: docker exec postgres psql -U postgres -d frauddb -c 'SELECT * FROM fraud_predictions ORDER BY prediction_time DESC LIMIT 10;'" -ForegroundColor Gray
Write-Host "  - Restart streaming: docker-compose restart spark-realtime-prediction" -ForegroundColor Gray
Write-Host ""
