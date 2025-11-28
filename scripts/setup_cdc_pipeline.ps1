# Wait for Kafka Connect to be ready
Write-Host "Waiting for Kafka Connect to be ready..."
$maxAttempts = 60
$attempt = 0

while ($attempt -lt $maxAttempts) {
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:8083/" -UseBasicParsing -TimeoutSec 5
        if ($response.StatusCode -eq 200) {
            Write-Host "Kafka Connect is ready!"
            break
        }
    }
    catch {
        Write-Host "Kafka Connect is not ready yet. Waiting... ($attempt/$maxAttempts)"
    }
    $attempt++
    Start-Sleep -Seconds 5
}

if ($attempt -eq $maxAttempts) {
    Write-Host "Timeout waiting for Kafka Connect to be ready."
    exit 1
}

# Register the Debezium PostgreSQL connector
Write-Host "Registering Debezium PostgreSQL connector..."
$configPath = "config/debezium/register-postgres-connector.json"
$config = Get-Content $configPath -Raw

try {
    $response = Invoke-RestMethod -Uri "http://localhost:8083/connectors/" `
        -Method Post `
        -ContentType "application/json" `
        -Body $config
    
    Write-Host "Connector registered successfully!"
    $response | ConvertTo-Json -Depth 10
}
catch {
    Write-Host "Error registering connector:"
    Write-Host $_.Exception.Message
}

# Check connector status
Write-Host "`nChecking connector status..."
Start-Sleep -Seconds 5

try {
    $status = Invoke-RestMethod -Uri "http://localhost:8083/connectors/postgres-transactions-connector/status"
    $status | ConvertTo-Json -Depth 10
    
    Write-Host "`nSetup complete! CDC pipeline is now active."
    Write-Host "Topic name: dbserver1.public.transactions"
}
catch {
    Write-Host "Error checking connector status:"
    Write-Host $_.Exception.Message
}
