# 🚀 Real-Time Fraud Detection - Quick Start

## 📋 Tổng quan

Hệ thống phát hiện gian lận **real-time** với flow:

```
PostgreSQL Transaction → Debezium CDC → Kafka → Spark Streaming → FastAPI ML → Slack Alert
```

**Đặc điểm:**

- ⚡ Phát hiện gian lận trong **<1 giây**
- 🔔 Alert **TẤT CẢ** giao dịch gian lận (không chỉ HIGH risk)
- 💬 Gửi Slack message với AI explanation
- 💾 Lưu vào database `fraud_predictions`

---

## ✅ Prerequisites

1. **Slack Webhook đã config** trong `.env`:

   ```bash
   SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
   ```

2. **Services đang chạy:**
   - PostgreSQL (transactions table)
   - Kafka + Debezium CDC
   - FastAPI (fraud-detection-api)
   - Spark Streaming (spark-realtime-prediction)

---

## 🚀 Khởi động

### **Bước 1: Start Real-Time Detection Service**

```powershell
docker-compose up -d spark-realtime-prediction
```

### **Bước 2: Verify Service Running**

```powershell
docker logs spark-realtime-prediction --tail 50
```

**Expected:**

```
✅ Streaming query started successfully
💬 Slack Alerts: Enabled
🎯 Alert Policy: ALL fraud detections (LOW/MEDIUM/HIGH)
⏳ Waiting for Kafka events...
```

### **Bước 3: Test với Transactions Giả**

```powershell
.\scripts\test-realtime-flow.ps1
```

Hoặc chạy SQL trực tiếp:

```powershell
docker exec postgres psql -U postgres -d frauddb -f /docker-entrypoint-initdb.d/test_realtime_flow.sql
```

---

## 📱 Kiểm tra Kết quả

### **1. Slack Alerts** (Real-time)

Mở Slack channel, bạn sẽ thấy **3 alerts**:

1. **🔴 HIGH RISK**

   ```
   Transaction: RT_HIGH_xxxxx
   Amount: $1,850.00
   Customer: John Doe
   Merchant: Suspicious Electronics Store
   Fraud Probability: 95.2%
   Risk Level: HIGH

   🤖 AI Analysis: Giao dịch xa 4000km, lúc 2h sáng, số tiền lớn
   ```

2. **🟡 MEDIUM RISK**

   ```
   Transaction: RT_MEDIUM_xxxxx
   Amount: $350.00
   Fraud Probability: 62.5%
   Risk Level: MEDIUM
   ```

3. **🟢 LOW RISK**
   ```
   Transaction: RT_LOW_xxxxx
   Amount: $85.00
   Fraud Probability: 45.3%
   Risk Level: LOW
   ```

### **2. Database Predictions**

```powershell
docker exec postgres psql -U postgres -d frauddb -c "
SELECT
    trans_num,
    prediction_score,
    is_fraud_predicted,
    model_version,
    prediction_time
FROM fraud_predictions
WHERE trans_num LIKE 'RT_%'
ORDER BY prediction_time DESC;
"
```

**Expected output:**

```
   trans_num     | prediction_score | is_fraud_predicted | model_version |   prediction_time
-----------------+------------------+--------------------+---------------+---------------------
 RT_HIGH_xxxxx   |           0.9520 |                  1 | mlflow_2      | 2025-12-10 15:30:45
 RT_MEDIUM_xxxxx |           0.6250 |                  1 | mlflow_2      | 2025-12-10 15:30:45
 RT_LOW_xxxxx    |           0.4530 |                  1 | mlflow_2      | 2025-12-10 15:30:45
```

### **3. Streaming Job Logs**

```powershell
docker logs spark-realtime-prediction -f
```

**Expected output:**

```
🔄 Batch 1: Processing 4 transactions
✅ Batch 1: Inserted 4 transactions to PostgreSQL

  RT_HIGH_xxxxx: Fraud=YES (95.2%), Risk=HIGH
  💾 Saved prediction to DB: RT_HIGH_xxxxx
  🚨 ALERT sent for RT_HIGH_xxxxx (HIGH risk)

  RT_MEDIUM_xxxxx: Fraud=YES (62.5%), Risk=MEDIUM
  💾 Saved prediction to DB: RT_MEDIUM_xxxxx
  🚨 ALERT sent for RT_MEDIUM_xxxxx (MEDIUM risk)

  RT_LOW_xxxxx: Fraud=YES (45.3%), Risk=LOW
  💾 Saved prediction to DB: RT_LOW_xxxxx
  🚨 ALERT sent for RT_LOW_xxxxx (LOW risk)

  RT_NORMAL_xxxxx: Fraud=NO (12.1%), Risk=LOW
  💾 Saved prediction to DB: RT_NORMAL_xxxxx

📊 Batch 1 Summary:
  Total transactions: 4
  Fraud detected: 3
  Predictions saved: 4
  Slack alerts sent: 3
```

---

## 🛠️ Troubleshooting

### **Không nhận được Slack alert**

1. Check webhook URL:

   ```powershell
   docker exec spark-realtime-prediction printenv SLACK_WEBHOOK_URL
   ```

2. Verify service config:

   ```powershell
   docker-compose config | Select-String "SLACK_WEBHOOK_URL"
   ```

3. Restart service:
   ```powershell
   docker-compose restart spark-realtime-prediction
   ```

### **Streaming job không xử lý transactions**

1. Check Kafka topic:

   ```powershell
   docker exec kafka kafka-topics --bootstrap-server localhost:9092 --list
   ```

   Should see: `postgres.public.transactions`

2. Check Debezium CDC:

   ```powershell
   docker logs debezium --tail 50
   ```

3. Verify Kafka messages:
   ```powershell
   docker exec kafka kafka-console-consumer `
     --bootstrap-server localhost:9092 `
     --topic postgres.public.transactions `
     --from-beginning `
     --max-messages 5
   ```

### **API prediction lỗi**

1. Check API health:

   ```powershell
   curl http://localhost:8000/health
   ```

2. Test prediction manually:

   ```powershell
   curl -X POST http://localhost:8000/predict/raw `
     -H "Content-Type: application/json" `
     -d '{"amt": 100.0, "hour": 14}'
   ```

3. Check API logs:
   ```powershell
   docker logs fraud-detection-api --tail 50
   ```

---

## 📊 Production Tips

### **Monitor Fraud Rate**

```sql
-- Fraud rate per hour
SELECT
    DATE_TRUNC('hour', prediction_time) AS hour,
    COUNT(*) AS total,
    SUM(is_fraud_predicted) AS fraud_count,
    ROUND(100.0 * SUM(is_fraud_predicted) / COUNT(*), 2) AS fraud_rate_pct
FROM fraud_predictions
WHERE prediction_time >= NOW() - INTERVAL '24 hours'
GROUP BY DATE_TRUNC('hour', prediction_time)
ORDER BY hour DESC;
```

### **High Risk Transactions**

```sql
SELECT
    fp.trans_num,
    t.amt,
    t.merchant,
    t.first || ' ' || t.last AS customer,
    fp.prediction_score,
    fp.prediction_time
FROM fraud_predictions fp
JOIN transactions t ON fp.trans_num = t.trans_num
WHERE fp.prediction_score > 0.7
  AND fp.prediction_time >= CURRENT_DATE
ORDER BY fp.prediction_score DESC;
```

### **Alert Statistics**

Check Slack channel for:

- Total alerts sent today
- Risk level distribution
- Response time (insert → alert)

---

## 🔗 Related Documentation

- [`docs/REALTIME_ARCHITECTURE.md`](../docs/REALTIME_ARCHITECTURE.md) - Chi tiết kiến trúc
- [`docs/FEATURES_EXPLAINED.md`](../docs/FEATURES_EXPLAINED.md) - Feature engineering
- [`sql/test_realtime_flow.sql`](../sql/test_realtime_flow.sql) - SQL test script
- [`scripts/test-realtime-flow.ps1`](../scripts/test-realtime-flow.ps1) - PowerShell test script

---

**🎯 Alert Policy:** Gửi Slack cho **TẤT CẢ** giao dịch gian lận (is_fraud=1), không phân biệt risk level. Color-coded: 🔴 HIGH, 🟡 MEDIUM, 🟢 LOW.
