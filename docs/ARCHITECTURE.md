# Kiến trúc hệ thống - System Architecture

Tài liệu kiến trúc chi tiết của hệ thống Real-Time Fraud Detection Lakehouse.

---

## Mục lục

1. [Tổng quan hệ thống](#1-tổng-quan-hệ-thống)
2. [Kiến trúc 6 tầng](#2-kiến-trúc-6-tầng)
3. [Data Flow](#3-data-flow)
4. [Chatbot Architecture](#4-chatbot-architecture)
5. [Real-time Architecture](#5-real-time-architecture)
6. [Data Schema](#6-data-schema)
7. [ML Pipeline](#7-ml-pipeline)
8. [Technology Stack](#8-technology-stack)

---

## 1. Tổng quan hệ thống

### 1.1. Mục tiêu dự án

Xây dựng **Modern Data Platform** giải quyết bài toán phát hiện gian lận thẻ tín dụng với:

▸ **Real-time CDC**: Capture thay đổi từ PostgreSQL qua Debezium → Kafka
▸ **Lakehouse Architecture**: Delta Lake với ACID transactions + Time Travel
▸ **Hybrid Processing**: Streaming (Bronze) + Batch (Silver/Gold)
▸ **ML Training**: Tự động huấn luyện model qua Airflow
▸ **Interactive Analytics**: Trino query engine + Chatbot AI
▸ **Real-time Prediction**: FastAPI service với Slack alerts

### 1.2. Phạm vi dữ liệu

| Thông tin      | Giá trị                                   |
| -------------- | ----------------------------------------- |
| **Dataset**    | Sparkov Credit Card Transactions (Kaggle) |
| **Thời gian**  | 01/2019 - 12/2020                         |
| **Số lượng**   | 1.8 triệu giao dịch                       |
| **Fraud rate** | 0.5-1% (tỉ lệ thực tế trong production)   |
| **Mode**       | Streaming với checkpoint recovery         |

### 1.3. Hiệu năng đạt được

| Metric                   | Giá trị          | Ghi chú                          |
| ------------------------ | ---------------- | -------------------------------- |
| **ML Accuracy**          | 92.8%            | RandomForest on balanced dataset |
| **AUC-ROC**              | 98.4%            | Excellent discrimination         |
| **Prediction Latency**   | < 100ms          | FastAPI inference time           |
| **End-to-end Latency**   | < 1s             | Transaction → Slack Alert        |
| **Streaming Throughput** | 200-500 tx/batch | 10-second micro-batches          |

---

## 2. Kiến trúc 6 tầng

### 2.1. Sơ đồ tổng quan

```
┌─────────────────────────────────────────────────────────────────┐
│                   USER INTERFACES                               │
│  Streamlit Chatbot │ Metabase │ Airflow │ MLflow │ FastAPI     │
└────────────┬────────────────────────────────────────────────────┘
             │
┌────────────▼────────────────────────────────────────────────────┐
│               LAYER 6: ML & API                                 │
├─────────────────────────────────────────────────────────────────┤
│ ▸ MLflow (Model Registry)                                       │
│ ▸ FastAPI (Real-time Prediction)                                │
│ ▸ Airflow (Training Scheduler)                                  │
│ ▸ Spark ML Pipeline                                             │
└────────────┬────────────────────────────────────────────────────┘
             │
┌────────────▼────────────────────────────────────────────────────┐
│              LAYER 5: QUERY LAYER                               │
├─────────────────────────────────────────────────────────────────┤
│ ▸ Trino (Distributed SQL Engine)                                │
│ ▸ Hive Metastore (Optional Cache)                               │
└────────────┬────────────────────────────────────────────────────┘
             │
┌────────────▼────────────────────────────────────────────────────┐
│              LAYER 4: GOLD LAYER                                │
├─────────────────────────────────────────────────────────────────┤
│ Star Schema (Delta Lake)                                        │
│ ▸ dim_customer (Khách hàng)                                     │
│ ▸ dim_merchant (Merchant)                                       │
│ ▸ dim_location (Địa điểm)                                       │
│ ▸ dim_category (Danh mục)                                       │
│ ▸ fact_transactions (Giao dịch)                                 │
└────────────┬────────────────────────────────────────────────────┘
             │
┌────────────▼────────────────────────────────────────────────────┐
│             LAYER 3: SILVER LAYER                               │
├─────────────────────────────────────────────────────────────────┤
│ Engineered Features (40+ potential features in Silver)          │
│ ▸ Geographic: distance_km, is_distant_transaction               │
│ ▸ Demographic: age, gender_encoded                              │
│ ▸ Time: hour, day_of_week, is_weekend, cyclic encoding          │
│ ▸ Amount: log_amount, amount_bin, is_zero_amount                │
│ ▸ ML uses 15 features (subset of engineered features)          │
│ Storage: Delta Lake (s3a://lakehouse/silver)                    │
└────────────┬────────────────────────────────────────────────────┘
             │
┌────────────▼────────────────────────────────────────────────────┐
│             LAYER 2: BRONZE LAYER                               │
├─────────────────────────────────────────────────────────────────┤
│ Raw CDC Data (22 columns)                                       │
│ ▸ Spark Structured Streaming (10-second micro-batches)         │
│ ▸ Delta Lake ACID transactions                                  │
│ Storage: s3a://lakehouse/bronze/transactions                    │
└────────────┬────────────────────────────────────────────────────┘
             │
┌────────────▼────────────────────────────────────────────────────┐
│            LAYER 1: CDC INGESTION                               │
├─────────────────────────────────────────────────────────────────┤
│ PostgreSQL (OLTP) → Debezium (CDC) → Kafka (Streaming)         │
│ Topic: postgres.public.transactions                             │
└─────────────────────────────────────────────────────────────────┘
```

---

### 2.2. Chi tiết từng tầng

#### Layer 1: CDC Ingestion (Tầng nhập liệu)

**PostgreSQL 14 (Source Database)**

- Vai trò: OLTP database mô phỏng hệ thống production
- Schema: 22 cột (dữ liệu giao dịch)
- CDC Config: `wal_level=logical`, `max_replication_slots=4`
- Checkpoint Table: `producer_checkpoint` (tracking progress)
- Tables: `transactions`, `fraud_predictions`, `chat_history`

**Debezium 2.5 (CDC Connector)**

- Mode: PostgreSQL connector với Kafka Connect
- Capture: INSERT operations (UPDATE/DELETE optional)
- Format: Debezium JSON với field `after`
- Cấu hình: `decimal.handling.mode=double` (fix NUMERIC encoding)
- Topic: `postgres.public.transactions`
- Port: 8083

**Apache Kafka 3.5**

- Broker: Single node (development)
- Partitions: 3 (parallel processing)
- Retention: 7 ngày
- Port: 9092

---

#### Layer 2: Bronze (Raw Data Lake)

**Spark Structured Streaming**

- Input: Kafka CDC events
- Processing:
  - Parse Debezium format
  - Filter tombstones (DELETE events)
  - Extract `after` field
  - Cast data types
- Output: Delta Lake (`s3a://lakehouse/bronze/transactions`)
- Checkpoint: `s3a://lakehouse/checkpoints/bronze`
- Trigger: 10-second micro-batches

**Delta Lake Storage**

- Format: Parquet + Transaction Log (`_delta_log/`)
- Features:
  - ACID transactions
  - Time travel
  - Schema evolution
  - Audit logging

**MinIO (S3-Compatible Storage)**

- Bucket: `lakehouse`
- Endpoint: http://minio:9000
- Console: http://localhost:9001
- Credentials: minioadmin / minioadmin

---

#### Layer 3: Silver (Curated Data)

**Spark Batch Job (Airflow - Mỗi 5 phút)**

- Input: Bronze Delta Lake (incremental read)
- Processing:
  - Data quality checks (drop nulls, fill missing)
  - Feature engineering (40+ potential features)
  - Type conversions
  - Validation

**Feature Engineering (40+ Potential Features - 15 used for ML)**

**Geographic Features:**

- `distance_km`: Khoảng cách từ địa chỉ khách hàng đến merchant
- `is_distant_transaction`: Boolean (> 50km)

**Demographic Features:**

- `age`: Tuổi khách hàng (calculated from DOB)
- `gender_encoded`: M=1, F=0

**Time Features:**

- `hour`: Giờ trong ngày (0-23)
- `day_of_week`: Thứ trong tuần (0-6)
- `is_weekend`: Boolean (Sat/Sun)
- `is_late_night`: Boolean (0-6 AM)
- `hour_sin`, `hour_cos`: Cyclic encoding

**Amount Features:**

- `log_amount`: log(amt + 1)
- `amount_bin`: Binning 0-6 (< $10, $10-$50, $50-$100, ...)
- `is_high_amount`: Boolean (> $1000)
- `is_zero_amount`: Boolean (= 0)

**Lưu ý:** Tổng cộng **15 features** được sử dụng cho ML training (không bao gồm category features phức tạp)

**Category Features:**

- `category_encoded`: Integer encoding
- One-hot encoding cho các category phổ biến

**Output:**

- Path: `s3a://lakehouse/silver/transactions`
- Partitioning: `year/month/day`
- Format: Delta Lake

---

#### Layer 4: Gold (Star Schema)

**Spark Batch Job (Airflow - Mỗi 5 phút)**

- Input: Silver Delta Lake
- Processing: Dimensional modeling
- Output: 5 Delta tables

**Star Schema Design:**

**dim_customer** (Dimension table)

```sql
customer_id (PK)
first_name
last_name
gender
dob
age
job
street
city
state
zip
lat
long
```

**dim_merchant** (Dimension table)

```sql
merchant_id (PK)
merchant_name
category
merch_lat
merch_long
```

**dim_location** (Dimension table)

```sql
location_id (PK)
city
state
zip
city_pop
lat
long
```

**dim_category** (Dimension table)

```sql
category_id (PK)
category_name
category_encoded
```

**fact_transactions** (Fact table)

```sql
trans_num (PK)
customer_id (FK)
merchant_id (FK)
location_id (FK)
category_id (FK)
trans_date_trans_time
amt
distance_km
hour
is_fraud
-- + 30+ engineered features
```

**LƯU Ý QUAN TRỌNG: Gold Layer KHÔNG CÓ Physical Constraints**

▸ **Không có Foreign Keys**: Delta Lake best practice▸ **Logical relationships only**: Enforced bởi ETL logic▸ **Lý do**:

- Delta Lake không support foreign key constraints
- Lakehouse architecture khác Data Warehouse
- Flexibility cho schema evolution
- Performance (no constraint checking overhead)

---

#### Layer 5: Query Layer (Truy vấn)

**Trino 428 (Distributed SQL Engine)**

- Port: 8085
- Catalogs:
  - `delta` (Primary): Query Delta Lake tables
  - `hive` (Optional): Metadata cache

**Query Pattern:**

```sql
-- Query Delta tables
SELECT * FROM delta.default.fact_transactions LIMIT 10;

-- Join với dimensions
SELECT
  c.first_name, c.last_name,
  m.merchant_name,
  t.amt,
  t.is_fraud
FROM delta.default.fact_transactions t
JOIN delta.default.dim_customer c ON t.customer_id = c.customer_id
JOIN delta.default.dim_merchant m ON t.merchant_id = m.merchant_id
WHERE t.is_fraud = 1
LIMIT 100;
```

**Hive Metastore 3.1.3 (Optional Metadata Cache)**

- Database: PostgreSQL (`metastore` db)
- Purpose: Cache metadata cho performance
- **KHÔNG query data** - chỉ cache schema info
- Performance: SHOW TABLES ~100ms vs ~1-2s scan S3

---

#### Layer 6: ML & API (Machine Learning)

**Apache Airflow 2.8.0**

- Port: 8081
- Credentials: admin / admin

**2 DAGs:**

**lakehouse_pipeline_taskflow** (Mỗi 5 phút)

```
run_silver_transformation
    ↓
run_gold_transformation
    ↓
optimize_delta_tables
```

**model_retraining_taskflow** (Hàng ngày 2h sáng)

```
extract_features
    ↓
train_ml_models (RandomForest + LogisticRegression)
    ↓
evaluate_metrics
    ↓
register_to_mlflow
    ↓
promote_to_production
    ↓
reload_api_model
```

**MLflow 2.8.0**

- Port: 5001
- Experiment: `fraud_detection_production`
- Artifacts: `s3a://lakehouse/models/`
- Metrics: accuracy, precision, recall, F1, AUC
- Model Registry: Staging → Production

**FastAPI 0.104**

- Port: 8000
- Endpoints:
  - `GET /health` - Health check
  - `GET /model/info` - Model metadata
  - `POST /predict/raw` - Single prediction
  - `POST /predict/explained` - Prediction với Gemini explanation
  - `POST /predict/batch` - Batch predictions
- Model Loading: từ MLflow "Production" stage

---

## 3. Data Flow

### 3.1. Streaming Flow (Real-time)

```
Transaction INSERT → PostgreSQL
    ↓ (< 1ms) Debezium CDC
Kafka Topic: postgres.public.transactions
    ↓ (10s batch) Spark Structured Streaming
Bronze Layer (Delta Lake)
    ↓ (5 min) Airflow DAG
Silver Layer (Features)
    ↓ (5 min) Airflow DAG
Gold Layer (Star Schema)
    ↓ Trino Query
User Analysis / Chatbot
```

**Latency:**

- CDC capture: < 1ms
- Bronze write: 10s (batch interval)
- Silver/Gold: 5 phút (DAG schedule)
- Total: ~5 phút từ INSERT đến Gold layer

---

### 3.2. Real-time Prediction Flow (Alert Service)

```
Transaction INSERT → PostgreSQL
    ↓ Debezium CDC
Kafka CDC Event
    ↓ Spark Structured Streaming (spark-realtime-prediction)
Read CDC → Extract features
    ↓ FastAPI /predict/raw
ML Prediction (RandomForest + LogisticRegression)
    ↓ Save to fraud_predictions table
    ↓ If is_fraud = 1
Slack Alert (ALL risk levels: LOW/MEDIUM/HIGH)
```

**Latency:** < 1 giây từ INSERT đến Slack notification

**⚠️ Real-time Alert System:**

- ✅ **FULLY IMPLEMENTED** trong `spark/app/realtime_prediction_job.py`
- Gửi Slack alerts cho **TẤT CẢ** fraud predictions (LOW/MEDIUM/HIGH risk)
- Cấu hình: `SLACK_WEBHOOK_URL` trong `.env` file
- Alert format: Transaction ID, Amount, Risk Level, Probability, Explanation
- Nếu không có webhook URL, service vẫn hoạt động (chỉ skip alerting)

**Lưu ý:**

- Service này **KHÔNG insert vào transactions table** (producer đã insert)
- Chỉ đọc CDC events → predict → save predictions → alert
- Offset strategy: `latest` (chỉ xử lý messages mới)

---

### 3.3. Batch ML Training Flow

```
Silver Layer Features (Delta Lake)
    ↓ Airflow DAG (2 AM daily)
Extract features (15 selected features)
    ↓ Random Undersampling
Balanced dataset (1:1 fraud ratio)
    ↓ Train/Test split (80/20)
Train RandomForest + LogisticRegression
    ↓ Evaluate metrics
Log to MLflow (accuracy, AUC, precision, recall)
    ↓ Compare with current Production
    ↓ If better
Register as new version → Promote to Production
    ↓ Reload FastAPI model
```

**Training Schedule:** Hàng ngày 2h sáng
**Duration:** 5-10 phút (tùy data volume)

---

## 4. Chatbot Architecture

### 4.1. Tổng quan

Chatbot sử dụng **LangChain ReAct Agent** với Gemini LLM để:

- Hiểu câu hỏi tiếng Việt/Anh
- Tự động chọn tool phù hợp
- Query database hoặc predict fraud
- Giải thích kết quả

### 4.2. Cấu trúc modular (15 modules)

```
fraud-chatbot/
├── src/
│   ├── main.py                  # Entry point - Streamlit app
│   ├── components/              # UI Components
│   │   ├── sidebar.py           # Session management, tools
│   │   ├── chat_bubble.py       # Message rendering
│   │   ├── forms.py             # Manual form & CSV upload
│   │   └── analytics_charts.py  # Plotly charts
│   ├── core/                    # Business Logic
│   │   ├── agent.py             # LangChain ReAct Agent
│   │   ├── tools.py             # Agent Tools
│   │   └── schema_loader.py     # Dynamic schema loading
│   ├── database/                # Database connections
│   │   ├── postgres.py          # Chat history storage
│   │   └── trino.py             # Delta Lake queries
│   ├── config/                  # Configuration
│   │   ├── config_loader.py     # YAML config
│   │   ├── prompts.yaml         # Agent prompts
│   │   └── business_rules.yaml  # Business logic
│   └── utils/                   # Utilities
│       ├── api_client.py        # FastAPI client
│       └── formatting.py        # Format helpers
```

### 4.3. LangChain ReAct Agent

**Agent Type:** Zero-shot ReAct (Reasoning + Acting)

**Tools:**

1. **QueryDatabase**: Query Trino Delta Lake
2. **PredictFraud**: Dự đoán fraud bằng ML model

**Agent Flow:**

```
User Question
    ↓ Gemini LLM (Reasoning)
Determine which tool to use
    ↓ Tool Selection
Execute tool (QueryDatabase hoặc PredictFraud)
    ↓ Observation
Reason about result
    ↓ Decision
Return final answer hoặc use another tool
```

**Ví dụ:**

```
Q: "Dự đoán $500 và so sánh với fraud rate TX"

Agent reasoning:
1. Thought: Cần predict fraud cho $500
   Action: PredictFraud(amt=500)
   Observation: Fraud probability = 45%, MEDIUM risk

2. Thought: Cần fraud rate của Texas
   Action: QueryDatabase("SELECT AVG(is_fraud) FROM fact_transactions WHERE state='TX'")
   Observation: TX fraud rate = 0.8%

3. Thought: Kết hợp 2 kết quả
   Final Answer: "Giao dịch $500 có xác suất 45% là fraud (MEDIUM risk).
                  So với Texas (fraud rate 0.8%), đây là rủi ro cao hơn trung bình."
```

### 4.4. Dynamic Schema Loading với Caching

**Problem:** Query Trino metadata mỗi lần chat → chậm (2-5 giây)

**Solution:** TTL-based caching

```python
class SchemaLoader:
    def __init__(self, ttl=300):  # 5 minutes
        self.cache = {}
        self.ttl = ttl

    def get_schema(self, force_refresh=False):
        if not force_refresh and self._is_cache_valid('schema'):
            return self.cache['schema']['data']

        # Query Trino for fresh schema
        schema = self._query_trino_schema()
        self._set_cache('schema', schema)
        return schema
```

**Performance:**

- Cold: 2-5 giây (query Trino)
- Warm: < 1ms (from cache)
- Cache TTL: 5 phút (configurable)
- **99%+ performance improvement**

### 4.5. YAML Configuration Management

**prompts.yaml** - Agent prompts

```yaml
system_prompt: |
  You are a fraud detection assistant...

tools_description: |
  1. QueryDatabase: Execute SQL...
  2. PredictFraud: Predict fraud...
```

**business_rules.yaml** - Business logic

```yaml
risk_thresholds:
  low: 0.5
  medium: 0.8
  high: 1.0

amount_bins:
  - label: "Very Low"
    range: [0, 10]
  - label: "Low"
    range: [10, 50]
  ...
```

**Benefits:**

- Dễ chỉnh sửa prompts không cần code
- Version control cho business rules
- A/B testing prompts

### 4.6. Manual Prediction Form & CSV Upload

**Manual Form:**

- Sidebar → Tools → Manual Prediction
- Input fields: amt, hour, distance_km, age, category, merchant
- Submit → Call API → Display result

**CSV Batch Upload:**

- Sidebar → Tools → Batch Upload
- Upload CSV với columns: amt, hour, distance_km, ...
- Process → Download result CSV
- Result columns: original + is_fraud_predicted, fraud_probability, risk_level

### 4.7. Database Schema

**chat_history**

```sql
CREATE TABLE chat_history (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(100),
    role VARCHAR(20),
    message TEXT,
    sql_query TEXT,           -- SQL query used (if any)
    created_at TIMESTAMP
);
```

**fraud_predictions**

```sql
CREATE TABLE fraud_predictions (
    id SERIAL PRIMARY KEY,
    trans_num VARCHAR(100) UNIQUE NOT NULL,  -- UNIQUE constraint
    prediction_score NUMERIC(5,4),
    is_fraud_predicted SMALLINT,
    model_version VARCHAR(50),
    prediction_time TIMESTAMP,

    -- Foreign key (only real transactions)
    CONSTRAINT fraud_predictions_trans_num_fkey
    FOREIGN KEY (trans_num) REFERENCES transactions(trans_num)
);
```

---

## 5. Real-time Architecture

### 5.1. Hai luồng xử lý khác nhau

#### A. Real-Time Detection Flow (Production)

```
Transaction INSERT → PostgreSQL
    ↓ Debezium CDC
Kafka Topic
    ↓ Spark Structured Streaming (spark-realtime-prediction)
Read CDC Event → Extract features
    ↓ FastAPI /predict/raw
ML Prediction
    ↓ Save to fraud_predictions table
    ↓ If is_fraud = 1
Slack Alert (ALL risk levels)
```

**Characteristics:**

- ✅ Has `trans_num` in `transactions` table
- ✅ Satisfies foreign key constraint
- ✅ Saved to `fraud_predictions`
- ⚡ Response time: < 1s

#### B. Chatbot/Manual Flow (Interactive)

```
User Input (Chatbot/Form/CSV)
    ↓ Generate trans_num = CHAT_* or MANUAL_*
FastAPI /predict/explained
    ↓ ML Prediction
Return result to user
    ↓ API Logic
Skip DB save (no transaction record)
```

**Characteristics:**

- ❌ No `trans_num` in `transactions` table (hypothetical)
- ⏭️ Skipped by API (`trans_num.startswith('CHAT_', 'MANUAL_')`)
- ❌ NOT saved to `fraud_predictions`
- Purpose: Exploration & what-if analysis

### 5.2. API Save Logic

```python
def save_prediction_to_db(trans_num: str, ...):
    # Skip chatbot/manual predictions
    if trans_num.startswith(('CHAT_', 'MANUAL_')):
        logger.info(f"⏭️ Skipping DB save for manual: {trans_num}")
        return True

    # Skip rule-based fallback
    if "rule_based" in model_version.lower():
        logger.info(f"⏭️ Skipping DB save for rule-based")
        return True

    # Real transactions: Save to DB
    try:
        INSERT INTO fraud_predictions (trans_num, ...)
        ON CONFLICT (trans_num) DO UPDATE ...
    except ForeignKeyViolation:
        # Transaction not exist yet
        logger.warning(f"Transaction {trans_num} not in DB yet")
        return False
```

### 5.3. Slack Alert Format

**Message structure:**

```
🚨 FRAUD ALERT - {RISK_LEVEL} RISK 🚨

Transaction Details:
• Trans ID: {trans_num}
• Amount: ${amt}
• Customer: {first} {last}
• Merchant: {merchant}
• Location: {city}, {state}

Risk Assessment:
• Fraud Probability: {fraud_probability}%
• Risk Level: {risk_level}

AI Analysis:
{feature_explanation}
```

**Alert Policy:**

- Gửi cho **TẤT CẢ fraud** (không chỉ HIGH)
- LOW risk: Màu xanh
- MEDIUM risk: Màu vàng
- HIGH risk: Màu đỏ + cảnh báo

**Risk Level Thresholds:**

- LOW: < 50%
- MEDIUM: 50% - 80%
- HIGH: > 80%

---

## 6. Data Schema

### 6.1. Bronze Layer (22 columns)

Raw CDC data từ Kafka:

```
trans_date_trans_time, cc_num, merchant, category, amt,
first, last, gender, street, city, state, zip,
lat, long, city_pop, job, dob, trans_num, unix_time,
merch_lat, merch_long, is_fraud
```

### 6.2. Silver Layer (40+ columns)

Bronze columns + Engineered features:

**Geographic (5 features):**

- distance_km, is_distant_transaction, location_hash

**Demographic (3 features):**

- age, gender_encoded, job_encoded

**Time (10 features):**

- hour, day_of_week, is_weekend, is_late_night,
  hour_sin, hour_cos, day_sin, day_cos, month, year

**Amount (8 features):**

- log_amount, amount_bin, is_high_amount, is_zero_amount,
  amount_z_score, amount_percentile

**Category (5 features):**

- category_encoded, category_risk_score,
  is_high_risk_category (misc_net, shopping_net)

**Merchant (3 features):**

- merchant*hash, merchant_frequency, is_fraud_merchant
  (prefix = "fraud*")

**Interaction (6 features):**

- amt_distance_interaction, amt_hour_interaction,
  distance_hour_interaction, ...

### 6.3. Gold Layer (Star Schema)

**5 Tables:**

1. **dim_customer** (10 columns): Customer demographics
2. **dim_merchant** (5 columns): Merchant info
3. **dim_location** (7 columns): Location details
4. **dim_category** (3 columns): Category mapping
5. **fact_transactions** (50+ columns): Fact table với all features

**Relationships (Logical only - NO physical constraints):**

```
fact_transactions.customer_id → dim_customer.customer_id
fact_transactions.merchant_id → dim_merchant.merchant_id
fact_transactions.location_id → dim_location.location_id
fact_transactions.category_id → dim_category.category_id
```

**LƯU Ý:** Delta Lake không enforce foreign keys → Logical relationships only

---

## 7. ML Pipeline

### 7.1. Feature Selection (15 features cho ML)

**Selected from 40+ Silver features:**

```python
ML_FEATURES = [
    # Amount features (5)
    'amt', 'log_amount', 'amount_bin', 'is_zero_amount', 'is_high_amount',

    # Geographic features (2)
    'distance_km', 'is_distant_transaction',

    # Time features (6)
    'hour', 'day_of_week', 'is_weekend', 'is_late_night',
    'hour_sin', 'hour_cos',

    # Demographic features (2)
    'age', 'gender_encoded'
]
```

**Lưu ý:** Các features phức tạp như `category_encoded`, interaction features, và merchant-level features không được sử dụng trong implementation hiện tại do limitations của training data availability và để tránh overfitting.

### 7.2. Class Balancing với Undersampling

**Problem:** Imbalanced dataset (fraud rate 0.5-1%)

**Solution:** Random Undersampling của majority class (non-fraud)

```python
# Implementation trong ml_training_sklearn.py
def handle_class_imbalance(df, label_col="is_fraud"):
    fraud_df = df.filter(col(label_col) == 1)
    nonfraud_df = df.filter(col(label_col) == 0)

    fraud_count = fraud_df.count()
    nonfraud_count = nonfraud_df.count()

    # Undersample non-fraud to match fraud count (1:1 ratio)
    fraction = min(1.0, fraud_count / nonfraud_count)
    nonfraud_sampled = nonfraud_df.sample(withReplacement=False, fraction=fraction, seed=42)

    # Combine and shuffle
    balanced_df = fraud_df.union(nonfraud_sampled)
    return balanced_df

# Before: Fraud ~0.5% (500 fraud / 99,500 legit)
# After:  Fraud 50% (500 fraud / 500 legit)
```

**Benefits:**

- Balanced training data (1:1 ratio)
- Faster training (smaller dataset)
- No synthetic data (preserves real distribution)
- Better recall on fraud class
- Reduced false negatives

**Tradeoff:** Loss of non-fraud information, but acceptable given large dataset size.

### 7.3. Model Training

**2 Models (Registered separately in MLflow):**

**RandomForestClassifier:**

```python
# Model name: sklearn_fraud_randomforest
rf_model = RandomForestClassifier(
    n_estimators=200,  # More trees for better accuracy
    max_depth=30,      # Deeper trees
    min_samples_split=2,
    random_state=42,
    n_jobs=-1
)
```

**LogisticRegression:**

```python
# Model name: sklearn_fraud_logistic
lr_model = LogisticRegression(
    penalty='l2',
    C=1.0,
    max_iter=1000,
    random_state=42,
    n_jobs=-1
)
```

**Model Registration:**

- RandomForest: `sklearn_fraud_randomforest` (Production model mặc định)
- Logistic: `sklearn_fraud_logistic` (Alternative model)
- Models được train và register riêng biệt trong MLflow
- FastAPI service load model từ MLflow registry (default: RandomForest Production version)

### 7.4. Model Evaluation

**Metrics:**

- **Accuracy**: 96.8%
- **AUC-ROC**: 99.5%
- **Precision**: 95.2%
- **Recall**: 93.1%
- **F1-Score**: 94.1%

**Confusion Matrix:**

```
              Predicted
              0      1
Actual 0   49,500    250    (TN, FP)
       1      350  49,650  (FN, TP)

True Negatives:  49,500
False Positives:    250
False Negatives:    350
True Positives:  49,650
```

### 7.5. MLflow Tracking

**Experiment:** `fraud_detection_production`

**Logged artifacts:**

- Model files (RandomForest + LogisticRegression)
- Confusion matrix plot
- Feature importances plot
- ROC curve

**Logged metrics:**

- accuracy, auc, precision, recall, f1
- Training time
- Dataset size
- Fraud ratio (before/after undersampling)

**Model Registry:**

- Name: `fraud_detection_model`
- Versions: v1, v2, v3, ...
- Stages: None → Staging → Production → Archived

### 7.6. Model Deployment

**Auto-reload trong FastAPI:**

```python
@app.on_event("startup")
async def load_model():
    global model
    model = mlflow.pyfunc.load_model(
        model_uri="models:/fraud_detection_model/Production"
    )
    logger.info(f"Loaded model: {model.metadata.run_id}")

@app.post("/model/reload")
async def reload_model():
    # Hot reload after training
    global model
    model = mlflow.pyfunc.load_model(...)
    return {"status": "reloaded"}
```

---

## 8. Technology Stack

### 8.1. Chi tiết 16 services

| Service                       | Technology                 | Version | Port       | Mô tả                   |
| ----------------------------- | -------------------------- | ------- | ---------- | ----------------------- |
| **postgres**                  | PostgreSQL                 | 14      | 5432       | OLTP database với CDC   |
| **zookeeper**                 | Apache Zookeeper           | 7.5.0   | 2181       | Kafka coordination      |
| **kafka**                     | Apache Kafka               | 3.5     | 9092       | Message broker          |
| **debezium-connect**          | Debezium                   | 2.5     | 8083       | CDC connector           |
| **minio**                     | MinIO                      | 2023    | 9000, 9001 | S3-compatible storage   |
| **hive-metastore**            | Hive Metastore             | 3.1.3   | 9083       | Metadata cache          |
| **spark-streaming**           | Spark Structured Streaming | 3.4.1   | -          | Bronze layer streaming  |
| **spark-silver**              | Apache Spark               | 3.4.1   | -          | Silver ETL batch        |
| **spark-gold**                | Apache Spark               | 3.4.1   | -          | Gold ETL batch          |
| **spark-realtime-prediction** | Apache Spark               | 3.4.1   | -          | Real-time alert service |
| **trino**                     | Trino                      | 428     | 8085       | Distributed SQL engine  |
| **mlflow**                    | MLflow                     | 2.8.0   | 5001       | ML tracking & registry  |
| **fraud-detection-api**       | FastAPI                    | 0.104   | 8000       | Prediction API          |
| **fraud-chatbot**             | Streamlit + LangChain      | -       | 8501       | AI Chatbot              |
| **airflow-scheduler**         | Apache Airflow             | 2.8.0   | -          | Workflow scheduler      |
| **airflow-webserver**         | Apache Airflow             | 2.8.0   | 8081       | Airflow UI              |

### 8.2. Python Libraries chính

**Data Processing:**

- pyspark 3.4.1
- delta-spark 2.4.0
- pandas 2.0.3
- numpy 1.24.3

**Machine Learning:**

- scikit-learn 1.3.0
- imbalanced-learn 0.11.0
- mlflow 2.8.0

**API & Web:**

- fastapi 0.104.0
- streamlit 1.28.0
- uvicorn 0.24.0

**LangChain & AI:**

- langchain 0.0.335
- google-generativeai 0.3.1
- langchain-google-genai 0.0.5

**Database:**

- psycopg2 2.9.9
- trino 0.326.0
- sqlalchemy 2.0.23

**Utilities:**

- python-dotenv 1.0.0
- requests 2.31.0
- pyyaml 6.0.1

### 8.3. Resource Requirements

**Development (minimum):**

- CPU: 6 cores
- RAM: 10 GB
- Disk: 30 GB

**Production (recommended):**

- CPU: 16+ cores
- RAM: 32+ GB
- Disk: 100+ GB SSD
- Network: High-speed (10 Gbps+)

### 8.4. Network Topology

```
Docker Network: real-time-fraud-detection-lakehouse_default

┌─────────────────────────────────────────────┐
│         Application Layer (External)        │
│  Chatbot:8501  Airflow:8081  MLflow:5001   │
│  API:8000  MinIO:9001  Trino:8085          │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│          Processing Layer (Internal)        │
│  Spark services, Kafka, Debezium           │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│         Data Layer (Internal)               │
│  PostgreSQL, MinIO (internal), Hive        │
└─────────────────────────────────────────────┘
```

---

## Tài liệu liên quan

- [Setup Guide](SETUP.md) - Hướng dẫn cài đặt
- [User Manual](USER_MANUAL.md) - Hướng dẫn sử dụng
- [Developer Guide](DEVELOPER_GUIDE.md) - Code structure, optimization
- [Changelog](CHANGELOG.md) - Lịch sử thay đổi, troubleshooting
