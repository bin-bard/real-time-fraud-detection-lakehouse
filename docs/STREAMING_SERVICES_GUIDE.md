# Streaming Services Guide

## Architecture

```
data-producer → PostgreSQL → Debezium CDC → Kafka
                                              ↓
                                    ┌─────────┴──────────┐
                                    ↓                    ↓
                          spark-streaming        spark-realtime-prediction
                          (Bronze Layer)         (Fraud Detection + Alert)
                                ↓                        ↓
                           Delta Lake              Slack Alerts
```

## Services

### 1. **spark-streaming** (Bronze Layer)

- **Purpose:** CDC events → Delta Lake (Bronze layer)
- **Input:** Kafka topic `postgres.public.transactions`
- **Output:** `s3a://lakehouse/bronze/transactions` (Delta format)
- **Checkpoint:** `s3a://lakehouse/checkpoints/bronze`

### 2. **spark-realtime-prediction** (Alert Service)

- **Purpose:** Fraud detection + Slack alerts
- **Input:** Kafka topic `postgres.public.transactions`
- **Flow:**
  1. Read CDC event from Kafka
  2. Insert to PostgreSQL `transactions` table (skip duplicates)
  3. Call FastAPI `/predict/raw`
  4. Save to `fraud_predictions` table
  5. Send Slack alert for ALL fraud (LOW/MEDIUM/HIGH)
- **Checkpoint:** `s3a://lakehouse/checkpoints/realtime-prediction`

## Offset Strategy

**Production Mode:** `startingOffsets: "latest"`

- ✅ Only process NEW messages after service starts
- ✅ No duplicate processing when restart
- ✅ Checkpoint tracks offset automatically
- ✅ Safe to stop/start anytime

**Development/Testing:** `startingOffsets: "earliest"` + clear checkpoints

- ⚠️ Reprocess ALL messages from beginning
- Use case: Initial load, testing full pipeline

## Setup from Scratch

### 1. Clone và start services

```powershell
# Clone project
git clone <repo-url>
cd real-time-fraud-detection-lakehouse

# Start all services
docker-compose up -d
```

### 2. Wait for initialization (2-3 minutes)

```powershell
# Check services status
docker-compose ps

# Wait for Debezium connector ready
docker logs -f debezium-connect | Select-String "Connector started"
```

### 3. Load initial data (optional)

```powershell
# data-producer sẽ tự động load data từ fraudTrain.csv
# Kiểm tra progress:
docker logs -f data-producer
```

### 4. Start streaming services

```powershell
# Services đã chạy từ docker-compose up
# Check logs:
docker logs -f spark-streaming          # Bronze layer
docker logs -f spark-realtime-prediction # Alert service
```

## Operations

### Restart Services (Recommended)

```powershell
# Restart without reprocessing old data
.\scripts\restart-streaming-services.ps1

# Restart and reprocess ALL data from beginning
.\scripts\restart-streaming-services.ps1 -ClearCheckpoints
```

### Manual Stop/Start

```powershell
# Stop services
docker-compose stop spark-streaming spark-realtime-prediction

# Start services (resume from last offset)
docker-compose start spark-streaming spark-realtime-prediction
```

### Check Logs

```powershell
# Bronze layer
docker logs -f spark-streaming | Select-String "Batch|Bronze"

# Alert service
docker logs -f spark-realtime-prediction | Select-String "Batch|NEW|Fraud|ALERT"
```

### Monitor Kafka Offset

```powershell
# List consumer groups
docker exec -it kafka kafka-consumer-groups.sh --bootstrap-server localhost:9092 --list

# Check offset lag
docker exec -it kafka kafka-consumer-groups.sh --bootstrap-server localhost:9092 --group <group-id> --describe
```

## Troubleshooting

### Issue: "New transactions: 0 (all duplicates)"

**Cause:** All messages already processed and exist in DB

**Solution:**

- Normal behavior in production (no new data)
- To test: Insert new transaction to PostgreSQL → CDC → Kafka → Alert

```sql
-- Manual test insert
INSERT INTO transactions (trans_date_trans_time, cc_num, merchant, category, amt, first, last, gender, street, city, state, zip, lat, long, city_pop, job, dob, trans_num, unix_time, merch_lat, merch_long, is_fraud)
VALUES (NOW(), 9999999999999999, 'Test Merchant', 'shopping_net', 999.99, 'Test', 'User', 'M', '123 Test St', 'TestCity', 'CA', 90001, 34.05, -118.25, 100000, 'Engineer', '1990-01-01', 'TEST_' || (random()*1000000)::int, EXTRACT(epoch FROM NOW())::int, 34.05, -118.25, 1);
```

### Issue: "Checkpoint already exists" or offset conflicts

**Solution:**

```powershell
# Clear checkpoints and restart
.\scripts\restart-streaming-services.ps1 -ClearCheckpoints
```

### Issue: Services crash after restart

**Check:**

1. MinIO accessible: `docker logs minio`
2. Kafka running: `docker-compose ps kafka`
3. Debezium connector active: `curl http://localhost:8083/connectors/postgres-connector/status`

**Fix:**

```powershell
# Restart dependent services
docker-compose restart kafka debezium-connect minio
Start-Sleep -Seconds 30

# Then restart streaming
.\scripts\restart-streaming-services.ps1
```

## Configuration

### Enable/Disable Slack Alerts

**docker-compose.yml:**

```yaml
spark-realtime-prediction:
  environment:
    SLACK_WEBHOOK_URL: "${SLACK_WEBHOOK_URL}" # Set to empty to disable
```

**.env:**

```bash
# Disable alerts
SLACK_WEBHOOK_URL=

# Enable alerts
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
```

### Adjust Batch Interval

**realtime_prediction_job.py:**

```python
.trigger(processingTime="10 seconds")  # Change to 5s, 30s, etc.
```

### Change Offset Strategy

**For testing (reprocess all):**

```python
.option("startingOffsets", "earliest")
```

**For production (new only):**

```python
.option("startingOffsets", "latest")
```

## Best Practices

1. **Production:** Always use `"latest"` offset
2. **Testing:** Use `-ClearCheckpoints` flag to reprocess data
3. **Monitoring:** Check logs regularly for errors
4. **Restart:** Use provided script instead of manual docker commands
5. **Checkpoints:** Keep checkpoints in production (tracked in MinIO)
6. **Backup:** Checkpoint data stored in `s3a://lakehouse/checkpoints/`

## File Structure

```
spark/app/
├── streaming_job.py              # Bronze layer (CDC → Delta)
└── realtime_prediction_job.py    # Alert service (Fraud detection)

scripts/
└── restart-streaming-services.ps1  # Safe restart script

services/
└── data-producer/
    └── producer.py                # Load data to PostgreSQL
```

## Expected Behavior

### Normal Operation

```
[Bronze] Batch X: Writing to Bronze layer... ✅
[Alert]  Batch Y: Processing 50 transactions
[Alert]  Batch Y: Inserted 50 NEW transactions
[Alert]  Fraud detected: 3
[Alert]  🚨 ALERT sent for TRANS_12345 (HIGH risk)
[Alert]  Slack alerts sent: 3
```

### No New Data

```
[Alert]  Batch Z: Processing 100 transactions
[Alert]  Batch Z: All 100 transactions already exist, skipping insert
[Alert]  New transactions: 0 (all duplicates)
[Alert]  Fraud detected: 0
```

This is **NORMAL** when:

- No new transactions from producer
- All Kafka messages already processed
- Services waiting for new CDC events
