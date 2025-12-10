# Real-Time Fraud Detection Architecture

## 📊 Kiến trúc tổng quan

### **1. Real-Time Detection Flow (< 1s)**

```
Kafka CDC → Bronze (Spark Streaming) → PostgreSQL transactions → FastAPI Prediction → fraud_predictions table
```

### **2. Chatbot/Manual Prediction Flow**

```
User Input → Chatbot/UI → FastAPI Prediction → Response (NOT saved to DB)
```

---

## 🔄 Data Flow Chi Tiết

### **A. Real-Time Flow (Production)**

1. **Transaction occurs** → Kafka CDC captures from source DB
2. **Bronze layer** (Spark Streaming) receives Kafka event
3. **Insert to PostgreSQL** `transactions` table
4. **Trigger prediction** → Call FastAPI `/predict/explained`
5. **Save prediction** → Insert to `fraud_predictions` table
6. **Alert if fraud** → Dashboard/notification

**Characteristics:**

- ✅ Has `trans_num` in `transactions` table
- ✅ Satisfies foreign key constraint
- ✅ Saved to `fraud_predictions`
- ⚡ Response time: < 1s

---

### **B. Chatbot/Manual Flow (Interactive)**

1. **User asks** → "Dự đoán giao dịch $850 lúc 2h sáng"
2. **Agent calls** → `PredictFraud` tool
3. **API predicts** → FastAPI with `trans_num = CHAT_*`
4. **Returns result** → Display in chatbot
5. **NOT saved** → API skips DB save (no transaction record)

**Characteristics:**

- ❌ No `trans_num` in `transactions` table (hypothetical)
- ⏭️ Skipped by API (`trans_num.startswith('CHAT_')`)
- ❌ NOT saved to `fraud_predictions`
- 🎯 Purpose: Exploration & what-if analysis

---

## 🗄️ Database Schema

### **fraud_predictions Table**

```sql
CREATE TABLE fraud_predictions (
    id SERIAL PRIMARY KEY,
    trans_num VARCHAR(100) UNIQUE NOT NULL,
    prediction_score NUMERIC(5,4),
    is_fraud_predicted SMALLINT,
    model_version VARCHAR(50),
    prediction_time TIMESTAMP DEFAULT NOW(),

    -- Foreign key: Only real transactions can be saved
    CONSTRAINT fraud_predictions_trans_num_fkey
    FOREIGN KEY (trans_num) REFERENCES transactions(trans_num)
);
```

**Purpose:** Store predictions for **real transactions only**

---

## 🔧 API Logic (fraud-detection-api)

### **save_prediction_to_db() Function**

```python
def save_prediction_to_db(trans_num: str, ...):
    # Skip chatbot/manual predictions
    if trans_num.startswith(('CHAT_', 'MANUAL_')):
        logger.info(f"⏭️ Skipping DB save for manual prediction: {trans_num}")
        return True  # Return success but don't save

    # Skip rule-based fallback
    if "rule_based" in model_ver.lower():
        logger.info(f"⏭️ Skipping DB save for rule-based")
        return True

    # Real transactions: Save to DB
    INSERT INTO fraud_predictions ...
```

---

## 🚀 Future Integration Steps

### **Step 1: Setup Kafka CDC**

- Configure Debezium connector for source database
- Topic: `transactions-topic`

### **Step 2: Spark Streaming Job**

```python
# bronze_streaming_job.py
df = spark.readStream \
    .format("kafka") \
    .option("subscribe", "transactions-topic") \
    .load()

# Parse and transform
transactions = df.selectExpr("CAST(value AS STRING)")

# Write to PostgreSQL
transactions.writeStream \
    .foreachBatch(lambda batch, _: insert_and_predict(batch)) \
    .start()

def insert_and_predict(batch_df):
    # 1. Insert to PostgreSQL transactions table
    batch_df.write.jdbc(...)

    # 2. Call FastAPI for each transaction
    for row in batch_df.collect():
        response = requests.post(
            "http://fraud-detection-api:8000/predict/explained",
            json=row.asDict()
        )
```

### **Step 3: Dashboard Real-Time Monitoring**

- Show live predictions from `fraud_predictions` table
- Alert on high-risk transactions
- Metrics: fraud rate, model performance

---

## 📈 Monitoring & Metrics

### **Queries for Monitoring**

```sql
-- Real-time prediction count (last 1 hour)
SELECT
    COUNT(*) as predictions_count,
    SUM(is_fraud_predicted) as fraud_count,
    model_version
FROM fraud_predictions
WHERE prediction_time > NOW() - INTERVAL '1 hour'
GROUP BY model_version;

-- Average prediction time
SELECT
    DATE_TRUNC('minute', prediction_time) as minute,
    COUNT(*) as predictions_per_minute,
    AVG(prediction_score) as avg_fraud_score
FROM fraud_predictions
WHERE prediction_time > NOW() - INTERVAL '1 hour'
GROUP BY minute
ORDER BY minute DESC;

-- High-risk transactions
SELECT *
FROM fraud_predictions fp
JOIN transactions t ON fp.trans_num = t.trans_num
WHERE fp.is_fraud_predicted = 1
  AND fp.prediction_score > 0.7
ORDER BY fp.prediction_time DESC
LIMIT 20;
```

---

## ✅ Current State

- ✅ API logic: Skip chatbot/manual predictions
- ✅ Database: Foreign key constraint preserved
- ✅ Chatbot: Works without DB save
- ⏳ Kafka integration: Pending
- ⏳ Spark streaming: Pending
- ⏳ Real-time dashboard: Pending

---

## 🎯 Benefits

1. **Data Integrity**: Foreign key ensures only valid transactions stored
2. **Flexibility**: Chatbot can predict hypothetical scenarios
3. **Scalability**: Ready for real-time Kafka integration
4. **Clean Separation**: Real vs Manual predictions clearly distinguished
5. **Performance**: Chatbot doesn't wait for DB writes

---

## 🚨 Alert Destinations

Khi phát hiện giao dịch **GIAN LẬN** (bất kỳ risk level nào: LOW/MEDIUM/HIGH), hệ thống sẽ gửi alert đến:

### **1. Slack Webhook** ⭐ (Đã triển khai)

**Configuration in `.env`:**

```bash
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/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
```

**Alert Policy:**

- ✅ **ALL fraud detections** (không chỉ HIGH)
- 🔴 HIGH RISK: fraud_probability > 70%
- 🟡 MEDIUM RISK: fraud_probability 40-70%
- 🟢 LOW RISK: fraud_probability < 40% but is_fraud=1

**Alert Format:**

```
🚨 FRAUD DETECTED 🔴

🔴 Fraud Alert - HIGH Risk

Transaction ID: T123456789
Amount: $1,850.00
Customer: John Doe
Merchant: Suspicious Electronics Store
Fraud Probability: 95.2%
Risk Level: HIGH

📍 Location: New York, NY

🤖 AI Analysis:
Giao dịch xa 4000km, lúc 2h sáng, số tiền lớn $1850.
Model phát hiện pattern bất thường.

⏰ Detected at: 2025-12-10 15:30:45
```

**Setup:**

1. ✅ Đã có Slack webhook URL trong `.env`
2. ✅ Service đã configure trong `docker-compose.yml`
3. ✅ Streaming job tự động gửi alert

---

### **2. PostgreSQL `fraud_predictions` Table** (Primary Storage)

Tất cả predictions được lưu vào database:

```sql
CREATE TABLE fraud_predictions (
    id SERIAL PRIMARY KEY,
    trans_num VARCHAR(100) UNIQUE NOT NULL,
    prediction_score NUMERIC(5, 4),
    is_fraud_predicted SMALLINT,
    model_version VARCHAR(50),
    prediction_time TIMESTAMP DEFAULT NOW(),

    CONSTRAINT fraud_predictions_trans_num_fkey
    FOREIGN KEY (trans_num) REFERENCES transactions(trans_num)
);
```

**Query predictions:**

```sql
-- All fraud predictions today
SELECT * FROM fraud_predictions
WHERE is_fraud_predicted = 1
  AND prediction_time >= CURRENT_DATE
ORDER BY prediction_score DESC;

-- HIGH risk only
SELECT
    fp.*,
    t.amt,
    t.merchant,
    t.first || ' ' || t.last AS customer
FROM fraud_predictions fp
JOIN transactions t ON fp.trans_num = t.trans_num
WHERE fp.prediction_score > 0.7
  AND fp.is_fraud_predicted = 1
ORDER BY fp.prediction_time DESC;
```

---

## ✅ Implementation Status

### **Completed:**

1. ✅ **Spark Streaming Job** (`spark/app/realtime_prediction_job.py`)

   - Reads from Kafka CDC
   - Inserts to PostgreSQL `transactions`
   - Calls FastAPI `/predict/raw`
   - Saves to `fraud_predictions`
   - Sends Slack alert for ALL fraud

2. ✅ **Docker Compose Service** (`spark-realtime-prediction`)

   - Auto-starts with dependencies
   - Configured with Slack webhook
   - 10-second micro-batching
   - Auto-restart enabled

3. ✅ **Alert Logic**

   - Policy: Alert on **ALL fraud** (is_fraud=1)
   - Color-coded by risk: 🔴 HIGH, 🟡 MEDIUM, 🟢 LOW
   - Rich Slack message with AI explanation

4. ✅ **Test Script** (`scripts/test-realtime-flow.ps1`)
   - Inserts 4 test transactions
   - Monitors streaming logs
   - Verifies database predictions
   - Checks Slack delivery

---

## 🚀 Quick Start

### **1. Start Real-Time Detection**

```powershell
# Start streaming service
docker-compose up -d spark-realtime-prediction

# Verify running
docker logs spark-realtime-prediction --tail 50
```

**Expected output:**

```
🚀 Starting Real-Time Fraud Detection Streaming...
📡 Kafka Broker: kafka:9092
📋 Kafka Topic: postgres.public.transactions
🔮 API Endpoint: http://fraud-detection-api:8000
💬 Slack Alerts: Enabled
🎯 Alert Policy: ALL fraud detections (LOW/MEDIUM/HIGH)
================================================================================
✅ Streaming query started successfully
⏳ Waiting for Kafka events...
```

### **2. Test with Sample Transactions**

```powershell
# Run test script
.\scripts\test-realtime-flow.ps1
```

**What happens:**

1. Inserts 4 transactions (3 fraud + 1 normal)
2. Debezium captures CDC events
3. Kafka receives messages
4. Spark Streaming processes batch
5. API predicts fraud probability
6. Saves to `fraud_predictions` table
7. **Sends 3 Slack alerts** (one for each fraud)

### **3. Verify Slack Alerts**

Check your Slack channel for 3 alerts:

- 🔴 **HIGH RISK**: $1,850 at Suspicious Electronics Store (distant + late night)
- 🟡 **MEDIUM RISK**: $350 at Regular Grocery Store (medium amount)
- 🟢 **LOW RISK**: $85 at Local Coffee Shop (small amount but flagged)

### **1. Slack Webhook** ⭐ (Khuyến nghị)

```yaml
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXX
```

**Setup:**

1. Tạo Slack App tại https://api.slack.com/apps
2. Add Incoming Webhook
3. Copy webhook URL vào `.env`

**Alert format:**

```
🚨 HIGH RISK FRAUD DETECTED 🚨

Transaction: T123456789
Amount: $1,200.50
Customer: John Doe
Merchant: Suspicious Shop
Risk: HIGH (95.2%)

Explanation: Giao dịch xa 200km, lúc 2h sáng, số tiền lớn
```

---

### **2. Email (SMTP)**

```yaml
SMTP_SERVER=smtp.gmail.com
SMTP_USER=alerts@company.com
SMTP_PASSWORD=app-password
ALERT_EMAIL=fraud-team@company.com
```

**Gmail setup:**

1. Enable 2FA
2. Generate App Password
3. Use App Password in `.env`

---

### **3. PostgreSQL Alert Queue** (Fallback)

Nếu Slack/Email fail, alert được lưu vào bảng [`alert_queue`](database/init_postgres.sql):

```sql
CREATE TABLE alert_queue (
    id SERIAL PRIMARY KEY,
    trans_num VARCHAR(100),
    alert_type VARCHAR(50),
    alert_data JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    processed BOOLEAN DEFAULT FALSE
);
```

**Manual review:**

```sql
SELECT * FROM alert_queue WHERE NOT processed ORDER BY created_at DESC;
```

---

### **4. Custom Webhook** (Advanced)

Gửi alert đến internal service:

```yaml
ALERT_WEBHOOK=http://your-internal-service:8080/alerts
```

**Payload:**

```json
{
  "trans_num": "T123456",
  "amt": 1200.5,
  "risk_level": "HIGH",
  "fraud_probability": 0.952,
  "explanation": "...",
  "customer": "John Doe",
  "merchant": "Suspicious Shop"
}
```

---

## ✅ Testing Alert Flow

### 1. Start services

```bash
docker-compose up -d spark-realtime-prediction alert-service
```

### 2. Insert test transaction (HIGH RISK)

```sql
INSERT INTO transactions (
    trans_date_trans_time, cc_num, merchant, category, amt,
    first, last, gender, street, city, state, zip,
    lat, long, city_pop, job, dob, trans_num, unix_time,
    merch_lat, merch_long, is_fraud
) VALUES (
    NOW(), 1234567890123456, 'Suspicious Shop', 'shopping_net', 1500.00,
    'John', 'Doe', 'M', '123 Main St', 'New York', 'NY', 10001,
    40.7128, -74.0060, 8000000, 'Engineer', '1990-01-01', 'TEST_001', EXTRACT(EPOCH FROM NOW()),
    35.0, -120.0,  -- 4000km away!
    1  -- Actual fraud
);
```

### 3. Check alerts

**Slack:** Check #fraud-alerts channel
**Email:** Check inbox
**Database:**

```sql
SELECT * FROM alert_queue ORDER BY created_at DESC LIMIT 1;
```

**Logs:**

```bash
docker logs spark-realtime-prediction --tail 50
docker logs alert-service --tail 50
```

### Bước 1: Tạo App (Từ màn hình bạn đang mở)

**Trong hộp thoại** **"Create an app"** **(như trong ảnh 1 của bạn):**

- **Chọn** **From scratch** **(Tùy chọn dưới cùng).**
- **App Name**: Đặt tên cho bot, ví dụ: **Fraud Alert Bot** **hoặc** **Fraud Detective**.
- **Pick a workspace to develop your app in**: Chọn Workspace Slack của công ty hoặc nhóm bạn.
- **Nhấn nút** **Create App**.

### Bước 2: Bật tính năng Webhook

**Sau khi tạo xong, bạn sẽ được đưa vào trang quản lý App.**

- **Nhìn menu bên tay trái, dưới mục** **Features**, chọn **Incoming Webhooks**.
- **Gạt công tắc** **Activate Incoming Webhooks** **sang** **On** **(Màu xanh).**

### Bước 3: Tạo Webhook URL cho kênh cụ thể

- **Kéo xuống dưới cùng trang đó, nhấn vào nút** **Add New Webhook to Workspace**.
- **Slack sẽ hỏi bạn muốn post vào kênh nào.**

  - **Khuyên dùng:** **Bạn nên tạo một kênh riêng trên Slack trước (ví dụ:** **#fraud-alerts**) để không làm phiền kênh chung.
  - **Chọn kênh đó trong danh sách (ví dụ:** **#general** **hoặc** **#fraud-alerts**).

- **Nhấn** **Allow**.

### Bước 4: Lấy URL và Cấu hình vào Project

**Sau khi nhấn Allow, bạn sẽ thấy một dòng** **Webhook URL** **mới hiện ra, có dạng:**
https://hooks.slack.com/services/T000.../B000.../XXXX...

- **Copy** **đường dẫn đó.**
- **Mở file cấu hình của bạn (thường là** **.env** **hoặc** **docker-compose.yml**) và dán vào biến môi trường **SLACK_WEBHOOK_URL**.
