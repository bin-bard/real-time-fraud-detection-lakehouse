# Setup From Scratch - Complete Guide

## Prerequisites

- Docker & Docker Compose
- Git
- PowerShell (Windows) hoặc Bash (Linux/Mac)
- Slack webhook URL (optional, for alerts)

## 1. Clone Project

```powershell
git clone https://github.com/bin-bard/real-time-fraud-detection-lakehouse.git
cd real-time-fraud-detection-lakehouse
```

## 2. Configure Environment

```powershell
# Copy example env file
cp .env.example .env

# Edit .env (optional)
# Set SLACK_WEBHOOK_URL for fraud alerts
```

## 3. Build & Start Services

```powershell
# Build and start all services
docker-compose up -d --build

# Wait 2-3 minutes for initialization
```

### Service Startup Order (Automatic via docker-compose)

1. **PostgreSQL** (5-10s)
   - Creates `frauddb` database
   - Initializes tables: `transactions`, `fraud_predictions`, `producer_checkpoint`
2. **Kafka + Zookeeper** (15-20s)
   - Kafka broker ready on port 9092
3. **Debezium Connect** (30-40s)
   - CDC connector auto-creates `postgres.public.transactions` topic
4. **MinIO** (5s)
   - Creates `lakehouse` bucket
5. **Fraud Detection API** (10s)

   - Loads ML model
   - Ready on port 8000

6. **Data Producer** (IDLE by default)

   - Container running, waiting for command
   - Does NOT auto-start streaming

7. **Spark Services**
   - `spark-realtime-prediction`: Alert service (auto-starts)
   - Uses `startingOffsets: "latest"` → Waits for NEW messages

## 4. Verify Services

```powershell
# Check all services running
docker-compose ps

# Expected output:
# NAME                        STATUS
# postgres                    Up (healthy)
# kafka                       Up
# debezium-connect            Up
# minio                       Up
# fraud-detection-api         Up
# data-producer               Up (IDLE)
# spark-realtime-prediction   Up
```

### Health Checks

```powershell
# PostgreSQL
docker exec -it postgres psql -U postgres -d frauddb -c "\dt"
# Expected: transactions, fraud_predictions, producer_checkpoint, chat_history

# Kafka topics
docker exec -it kafka kafka-topics.sh --bootstrap-server localhost:9092 --list
# Expected: postgres.public.transactions

# Debezium connector
curl http://localhost:8083/connectors/postgres-connector/status
# Expected: "state": "RUNNING"

# API health
curl http://localhost:8000/health
# Expected: {"status": "ok", "model_loaded": true}

# MinIO
docker exec -it minio mc ls minio/lakehouse/
# Expected: bronze/, checkpoints/
```

## 5. Load Initial Data (Optional)

### Option A: Bulk Load (Fast - for testing)

```powershell
# Load 50,000 transactions in ~30 seconds
docker exec data-producer python producer.py --bulk-load 50000

# Check progress
docker logs -f data-producer
```

### Option B: Streaming Mode (Real-time simulation)

```powershell
# Start streaming with delay between transactions
docker exec -d data-producer python producer.py --stream --delay 0.1

# Monitor
docker logs -f data-producer
```

### Option C: Auto-load on startup (Permanent)

Edit `docker-compose.yml`:

```yaml
data-producer:
  # ... existing config ...
  command: python producer.py --stream --delay 0.1 # Auto-start streaming
```

Then restart:

```powershell
docker-compose restart data-producer
```

## 6. Monitor Real-Time Alert Flow

```powershell
# Watch alert service logs
docker logs -f spark-realtime-prediction | Select-String "Batch|NEW|Fraud|ALERT"

# Expected output when new transactions arrive:
# 🔄 Batch 1: Processing 100 transactions
# ✅ Batch 1: Inserted 100 NEW transactions
# Fraud detected: 3
# 🚨 ALERT sent for TRANS_12345 (HIGH risk)
# Slack alerts sent: 3
```

## 7. Test Alert Manually

Insert a fraud transaction to trigger alert:

```sql
-- Connect to PostgreSQL
docker exec -it postgres psql -U postgres -d frauddb

-- Insert test fraud transaction
INSERT INTO transactions (
    trans_date_trans_time, cc_num, merchant, category, amt,
    first, last, gender, street, city, state, zip,
    lat, long, city_pop, job, dob, trans_num, unix_time,
    merch_lat, merch_long, is_fraud
) VALUES (
    NOW(), 9999999999999999, 'FRAUD_TEST_MERCHANT', 'shopping_net', 999.99,
    'TestFraud', 'User', 'M', '123 Test St', 'TestCity', 'CA', 90001,
    34.05, -118.25, 100000, 'Engineer', '1990-01-01',
    'FRAUD_TEST_' || EXTRACT(epoch FROM NOW())::bigint,
    EXTRACT(epoch FROM NOW())::int,
    34.05, -118.25, 1
);
```

Within 10-20 seconds:

1. ✅ Debezium CDC captures INSERT
2. ✅ Kafka receives message
3. ✅ Spark streaming processes transaction
4. ✅ API prediction called
5. ✅ Slack alert sent (if configured)

Check logs:

```powershell
docker logs spark-realtime-prediction --tail 50 | Select-String "FRAUD_TEST"
```

## 8. Stop/Start Services (Production)

### Stop All Services

```powershell
docker-compose stop
```

### Start All Services (Resume from checkpoint)

```powershell
docker-compose start

# Services resume automatically:
# - Producer continues from last checkpoint (producer_checkpoint table)
# - Spark streaming continues from last Kafka offset (checkpoints in MinIO)
# - No data loss, no duplicates
```

### Restart Specific Services

```powershell
# Restart alert service only
cd scripts
.\restart-streaming-services.ps1

# Restart with checkpoint clear (reprocess all data)
.\restart-streaming-services.ps1 -ClearCheckpoints
```

## 9. Clean Shutdown

```powershell
# Stop all services
docker-compose down

# Remove volumes (⚠️ DELETES ALL DATA)
docker-compose down -v
```

## Common Issues & Fixes

### Issue 1: "All transactions already exist, skipping insert"

**Cause:** Producer has loaded data, but Spark restarted with `latest` offset (only new messages)

**Fix:** This is NORMAL behavior. To test alerts:

1. Insert manual test transaction (see step 7)
2. OR restart producer: `docker exec -d data-producer python producer.py --stream --delay 0.1`

### Issue 2: Services not starting

**Check dependencies:**

```powershell
# PostgreSQL must be up first
docker logs postgres | Select-String "ready to accept"

# Kafka must be ready
docker logs kafka | Select-String "started"

# Debezium connector must be running
curl http://localhost:8083/connectors/postgres-connector/status
```

**Fix:**

```powershell
# Restart in order
docker-compose restart postgres
Start-Sleep -Seconds 10

docker-compose restart kafka
Start-Sleep -Seconds 20

docker-compose restart debezium-connect
Start-Sleep -Seconds 30

docker-compose restart spark-realtime-prediction
```

### Issue 3: Checkpoint errors

**Clear checkpoints:**

```powershell
cd scripts
.\restart-streaming-services.ps1 -ClearCheckpoints
```

### Issue 4: Producer stuck at checkpoint

**Reset producer:**

```sql
-- Connect to PostgreSQL
docker exec -it postgres psql -U postgres -d frauddb

-- Reset checkpoint to beginning
UPDATE producer_checkpoint SET last_line_processed = 0, last_trans_num = NULL WHERE id = 1;
```

Then restart producer:

```powershell
docker-compose restart data-producer
docker exec -d data-producer python producer.py --stream --delay 0.1
```

## Architecture Summary

```
┌──────────────┐
│ fraudTrain.csv│
└───────┬──────┘
        │
        ↓
┌──────────────┐      ┌──────────────┐
│data-producer │ ───→ │ PostgreSQL   │
│(checkpoint)  │      │ transactions │
└──────────────┘      └───────┬──────┘
                              │
                              │ (CDC)
                              ↓
                      ┌──────────────┐
                      │ Debezium     │
                      │ Kafka Topic  │
                      └───────┬──────┘
                              │
                              ↓
                   ┌──────────────────────┐
                   │spark-realtime-pred   │
                   │(Fraud Detection)     │
                   └──────┬───────────────┘
                          │
                   ┌──────┴─────────┐
                   ↓                ↓
           ┌──────────────┐  ┌──────────┐
           │fraud_predictions│ │  Slack   │
           │   (PostgreSQL)  │ │  Alerts  │
           └──────────────┘  └──────────┘
```

## Key Features

✅ **Idempotent:** Safe to restart anytime
✅ **Checkpointed:** Producer & Spark track progress
✅ **No Duplicates:** LEFT ANTI JOIN prevents duplicate inserts
✅ **Latest Offset:** Only process NEW messages after restart
✅ **Real-time:** < 1 second fraud detection + alert
✅ **Production Ready:** Handles stop/start gracefully

## Next Steps

- Configure Slack webhook for alerts
- Load full dataset: `docker exec data-producer python producer.py --bulk-load 578500`
- Monitor Spark logs: `docker logs -f spark-realtime-prediction`
- Query predictions: `docker exec -it postgres psql -U postgres -d frauddb -c "SELECT * FROM fraud_predictions LIMIT 10"`
- Check Slack channel for fraud alerts 🚨

## Support

- Documentation: `docs/STREAMING_SERVICES_GUIDE.md`
- Architecture: `docs/REALTIME_ARCHITECTURE.md`
- Scripts: `scripts/restart-streaming-services.ps1`
