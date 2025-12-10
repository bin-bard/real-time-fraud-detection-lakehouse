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
