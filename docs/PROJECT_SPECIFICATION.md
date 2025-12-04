# ĐẶC TẢ KỸ THUẬT DỰ ÁN

**Tên đề tài:** Xây dựng hệ thống Data Lakehouse phát hiện gian lận tài chính theo thời gian thực

**Nhóm thực hiện:** Nhóm 6

**Thành viên:**

1. Nguyễn Thanh Tài - 22133049
2. Võ Triệu Phúc - 22133043

**GVHD:** ThS. Phan Thị Thể

**Phiên bản:** 6.0 - Final Implementation

---

## 1. TỔNG QUAN DỰ ÁN

### 1.1. Mục tiêu

Xây dựng **Modern Data Platform** giải quyết bài toán phát hiện gian lận thẻ tín dụng với các tính năng:

1. **Real-time CDC**: Capture thay đổi từ PostgreSQL qua Debezium → Kafka
2. **Lakehouse Architecture**: Delta Lake với ACID transactions + Time Travel
3. **Hybrid Processing**: Streaming (Bronze) + Batch (Silver/Gold)
4. **ML Training**: Tự động huấn luyện model qua Airflow
5. **Interactive Analytics**: Trino query engine + Metabase dashboard
6. **Real-time Prediction API**: FastAPI service với MLflow model integration

### 1.2. Phạm vi dữ liệu

- **Dataset**: Sparkov Credit Card Transactions (Kaggle)
- **Thời gian**: 01/2019 - 12/2020 (1.8 triệu giao dịch)
- **Fraud rate**: 0.5-1% (tỉ lệ thực tế trong production)
- **Streaming mode**: Mô phỏng real-time với checkpoint recovery

---

## 2. KIẾN TRÚC HỆ THỐNG

### 2.1. Tổng quan Architecture

```
┌──────────────────────────────────────────────────────────────┐
│ Layer 1: Nhập dữ liệu (CDC Pipeline)                        │
├──────────────────────────────────────────────────────────────┤
│ PostgreSQL 14 (Source DB - OLTP)                             │
│     ↓ Debezium 2.5 (CDC Connector)                           │
│ Apache Kafka (Message Broker)                                │
│     ↓ Topic: postgres.public.transactions                    │
└──────────────────────────────────────────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────────┐
│ Layer 2: Bronze - Raw Data Lake (Streaming)                 │
├──────────────────────────────────────────────────────────────┤
│ Spark Structured Streaming (Liên tục)                        │
│ Input: Kafka CDC events                                      │
│ Processing: Parse Debezium format, filter tombstones         │
│ Output: s3a://lakehouse/bronze/transactions                  │
│ Format: Delta Lake (ACID + Time Travel)                      │
│ Storage: MinIO (S3-compatible object storage)                │
└──────────────────────────────────────────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────────┐
│ Layer 3: Silver - Curated Data (Batch ETL)                  │
├──────────────────────────────────────────────────────────────┤
│ Spark Batch Job (Airflow - Mỗi 5 phút)                      │
│ Input: Bronze Delta Lake (đọc incremental)                  │
│ Processing:                                                  │
│   - Kiểm tra chất lượng dữ liệu (drop nulls, fill missing)  │
│   - Feature engineering (40 features)                        │
│     * Geographic: distance_km, is_distant_transaction        │
│     * Demographic: age, gender_encoded                       │
│     * Time: hour, day_of_week, is_weekend, cyclic encoding   │
│     * Amount: log_amount, amount_bin, is_zero_amount         │
│ Output: s3a://lakehouse/silver/transactions                  │
└──────────────────────────────────────────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────────┐
│ Layer 4: Gold - Star Schema (Batch ETL)                     │
├──────────────────────────────────────────────────────────────┤
│ Spark Batch Job (Airflow - Mỗi 5 phút)                      │
│ Input: Silver Delta Lake                                     │
│ Processing: Mô hình hóa chiều (Dimensional modeling)         │
│ Output: 5 bảng Delta                                         │
│   - dim_customer (Chiều khách hàng)                          │
│   - dim_merchant (Chiều merchant)                            │
│   - dim_time (Chiều thời gian)                               │
│   - dim_location (Chiều địa điểm)                            │
│   - fact_transactions (Fact giao dịch)                       │
└──────────────────────────────────────────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────────┐
│ Layer 5: Query & Consumption                                │
├──────────────────────────────────────────────────────────────┤
│ Trino Query Engine (Port 8085)                              │
│   ├─ Delta Catalog (Primary): Query dữ liệu từ _delta_log/  │
│   └─ Hive Catalog (Optional): Metadata cache cho SHOW TABLES│
│                                                              │
│ Hive Metastore 3.1.3 (Metadata Cache - Optional)            │
│   - Vai trò: Tăng tốc discovery operations (~100ms)         │
│   - KHÔNG dùng để query data (Delta connector đọc S3)       │
│                                                              │
│ Metabase (BI Dashboard)                                     │
│   - Connection: jdbc:trino://trino:8081/delta               │
│   - Queries: delta.gold.*, delta.silver.*, delta.bronze.*   │
└──────────────────────────────────────────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────────┐
│ Layer 6: ML & API Services                                  │
├──────────────────────────────────────────────────────────────┤
│ Apache Airflow 2.8.0 (Workflow Orchestration)               │
│   DAG 1: lakehouse_pipeline_taskflow (Mỗi 5 phút)           │
│     - run_silver_transformation                              │
│     - run_gold_transformation                                │
│   DAG 2: model_retraining_taskflow (Hàng ngày 2 AM)         │
│     - train_ml_models (RandomForest + LogisticRegression)    │
│                                                              │
│ MLflow 2.8.0 (Model Tracking & Registry)                    │
│   - Experiment: fraud_detection_production                   │
│   - Artifacts: s3a://lakehouse/models/                       │
│   - Metrics: accuracy, precision, recall, F1, AUC            │
│                                                              │
│ FastAPI 3.0.0 (Real-time Prediction API - Port 8000)        │
│   - Load models từ MLflow Model Registry                     │
│   - /predict - Dự đoán đơn lẻ                                │
│   - /predict/batch - Dự đoán hàng loạt                       │
│   - /model/reload - Hot reload model sau training            │
│   - Rule-based fallback nếu MLflow chưa có model             │
└──────────────────────────────────────────────────────────────┘
```

### 2.2. Chi tiết các thành phần

#### 2.2.1. Data Ingestion Layer (Tầng nhập liệu)

**PostgreSQL 14 (Source Database)**

- Vai trò: OLTP database mô phỏng hệ thống production
- Schema: 22 cột (dữ liệu giao dịch)
- CDC Config: `wal_level=logical`, `max_replication_slots=4`
- Checkpoint Table: `producer_checkpoint` (theo dõi tiến trình data producer)

**Debezium 2.5 (CDC Connector)**

- Mode: PostgreSQL connector với Kafka Connect
- Capture: INSERT operations (UPDATE/DELETE optional)
- Format: Debezium JSON với field `after`
- Cấu hình đặc biệt: `decimal.handling.mode=double` (sửa lỗi NUMERIC encoding)
- Topic: `postgres.public.transactions`

**Apache Kafka**

- Broker: Single node (môi trường dev)
- Partitions: 3 (cho parallel processing)
- Retention: 7 ngày
- UI: Kafka UI trên port 9002

#### 2.2.2. Storage Layer (Tầng lưu trữ)

**MinIO (S3-Compatible Object Storage)**

- Bucket: `lakehouse`
- Cấu trúc thư mục:
  - `/bronze/transactions/` - Dữ liệu CDC thô
  - `/silver/transactions/` - Dữ liệu đã feature engineering
  - `/gold/dim_*/` - Bảng chiều (Dimension tables)
  - `/gold/fact_*/` - Bảng fact
  - `/checkpoints/` - Spark streaming checkpoints
  - `/models/` - MLflow artifacts
- Access: `minio` / `minio123`
- Endpoint: http://minio:9000

**Delta Lake 2.4.0**

- Format: Parquet + Transaction Log (`_delta_log/`)
- Tính năng:
  - ACID transactions
  - Time travel (lịch sử version)
  - Schema evolution (tiến hóa schema)
  - Audit logging (ghi log kiểm toán)
  - Compaction (OPTIMIZE command)
  - Vacuum (retention period)
- Chiến lược phân vùng:
  - Bronze/Silver: `year/month/day`
  - Gold: Không phân vùng (dimensions nhỏ)

**Hive Metastore 3.1.3 (Optional Metadata Cache)**

- Database: PostgreSQL (`metastore` db)
- Mục đích: Metadata cache cho Trino
- Performance: SHOW TABLES ~100ms (so với ~1-2s scan S3 trực tiếp)
- **KHÔNG dùng để query data** - chỉ cache thông tin schema
- Đăng ký tự động: `register_tables_to_hive.py` (kích hoạt thủ công)

#### 2.2.3. Processing Layer (Tầng xử lý)

**Apache Spark 3.4.1**

- Mode: Spark Standalone Cluster
- Thành phần:
  - 1 Master node (resource manager)
  - 1 Worker node (executor)
- Cấu hình:
  - `spark.sql.extensions=io.delta.sql.DeltaSparkSessionExtension`
  - `spark.sql.catalog.spark_catalog=org.apache.spark.sql.delta.catalog.DeltaCatalog`
  - S3A credentials: `minio` / `minio123`
  - Delta Lake JARs: pre-installed trong custom image

**Các công việc xử lý:**

1. **Bronze Streaming** (`streaming_job.py`)

   - Mode: Streaming liên tục
   - Trigger: `availableNow=False` (liên tục)
   - CPU: ~195% (bình thường cho streaming)
   - Tự động khởi động: Docker compose `depends_on`

2. **Silver Batch** (`silver_job.py`)

   - Mode: Batch ETL
   - Trigger: Airflow mỗi 5 phút
   - Processing: Incremental (watermark-based)
   - CPU: 0% khi sleep, tăng đột biến khi chạy

3. **Gold Batch** (`gold_job.py`)

   - Mode: Batch ETL
   - Trigger: Airflow mỗi 5 phút sau Silver
   - Processing: Chuyển đổi star schema
   - Output: 5 bảng Delta

4. **ML Training** (`ml_training_job.py`)
   - Mode: Batch ML
   - Trigger: Airflow hàng ngày lúc 2 AM
   - Models: RandomForest + LogisticRegression
   - Tracking: MLflow experiment

#### 2.2.4. Query Layer (Tầng truy vấn)

**Trino (Query Engine)**

- Version: Latest stable
- Port: 8081 (internal), 8085 (external)
- Catalogs:
  - **`delta`** - Catalog chính (query dữ liệu)
  - **`hive`** - Metadata cache (chỉ list tables)
- Memory: 2GB heap (có thể cấu hình)
- Parallelism: 4 workers

**Mẫu truy vấn:**

```sql
-- ✅ ĐÚNG - Query data qua Delta catalog
SELECT * FROM delta.gold.fact_transactions;

-- ✅ OK - List tables qua Hive cache
SHOW TABLES FROM hive.gold;

-- ❌ SAI - Query data qua Hive (không hỗ trợ Delta format)
-- SELECT * FROM hive.gold.fact_transactions; -- Error!
```

#### 2.2.5. Orchestration Layer (Tầng điều phối)

**Apache Airflow 2.8.0**

- Mode: Docker Compose deployment
- Thành phần:
  - Webserver: UI trên port 8081
  - Scheduler: Thực thi task
  - Database: PostgreSQL (`airflow` db)
  - Executor: LocalExecutor
- Xác thực: `admin` / `admin`

**DAGs:**

1. `lakehouse_pipeline_taskflow` (Mỗi 5 phút)

   - check_bronze_data
   - run_silver_transformation
   - run_gold_transformation
   - verify_trino
   - send_pipeline_summary

2. `model_retraining_taskflow` (Hàng ngày 2 AM)
   - check_data_availability
   - train_ml_models
   - verify_mlflow
   - send_notification

#### 2.2.6. ML API Layer (Tầng API Machine Learning)

**FastAPI 3.0.0 (Real-time Prediction Service)**

- Port: 8000 (external)
- Mục đích: API endpoint cho dự đoán gian lận real-time
- Tính năng chính:

**1. Model Loading:**

```python
# Tự động load model từ MLflow khi khởi động
def load_model_from_mlflow():
    # Ưu tiên: MLflow Model Registry
    # Fallback: Latest experiment run
    # Last resort: Rule-based prediction
```

**2. Endpoints:**

| Endpoint         | Method | Mô tả                                   |
| ---------------- | ------ | --------------------------------------- |
| `/health`        | GET    | Kiểm tra trạng thái service             |
| `/model/info`    | GET    | Xem metrics model (accuracy, AUC, etc.) |
| `/predict`       | POST   | Dự đoán đơn lẻ với 20 features          |
| `/predict/batch` | POST   | Dự đoán hàng loạt nhiều giao dịch       |
| `/model/reload`  | POST   | Hot reload model sau training mới       |

**3. Input Schema (20 features):**

```python
class TransactionFeatures(BaseModel):
    # Transaction features
    amt: float
    log_amount: float
    amount_bin: int
    is_zero_amount: int
    is_high_amount: int

    # Geographic features
    distance_km: float
    is_distant_transaction: int

    # Demographic features
    age: int
    gender_encoded: int

    # Time features
    hour: int
    day_of_week: int
    is_weekend: int
    is_late_night: int
    hour_sin: float
    hour_cos: float
```

**4. Response Schema:**

```python
class PredictionResponse(BaseModel):
    trans_num: Optional[str]
    is_fraud_predicted: int         # 0 hoặc 1
    fraud_probability: float        # 0.0 đến 1.0
    risk_level: str                 # LOW, MEDIUM, HIGH
    model_version: str              # Tracking model version
```

**5. Fallback Strategy:**

- **Primary**: MLflow model (RandomForest/LogisticRegression)
- **Fallback**: Rule-based prediction khi MLflow unavailable
  - Quy tắc: High amount + Distant + Late night → High risk
  - Đảm bảo service luôn sẵn sàng dù model chưa training

**6. Use Cases:**

- **Alert System**: Gọi API real-time → Gửi cảnh báo nếu HIGH risk
- **Dashboard Integration**: Metabase hiển thị predictions
- **Manual Review**: Nhân viên kiểm tra giao dịch nghi ngờ
- **Batch Processing**: Xử lý đợt lớn transactions overnight

---

## 3. DATA SCHEMA & PROCESSING

### 3.1. Bronze Layer (Raw CDC)

**Nguồn:** Kafka topic `postgres.public.transactions`

**Định nghĩa Schema (22 cột):**

```python
schema = StructType([
    StructField("trans_date_trans_time", StringType()),
    StructField("cc_num", StringType()),
    StructField("merchant", StringType()),
    StructField("category", StringType()),
    StructField("amt", DoubleType()),
    StructField("first", StringType()),
    StructField("last", StringType()),
    StructField("gender", StringType()),
    StructField("street", StringType()),
    StructField("city", StringType()),
    StructField("state", StringType()),
    StructField("zip", StringType()),
    StructField("lat", DoubleType()),
    StructField("long", DoubleType()),
    StructField("city_pop", StringType()),
    StructField("job", StringType()),
    StructField("dob", StringType()),
    StructField("trans_num", StringType()),
    StructField("unix_time", StringType()),
    StructField("merch_lat", DoubleType()),
    StructField("merch_long", DoubleType()),
    StructField("is_fraud", StringType())
])
```

**Logic xử lý:**

1. Đọc từ Kafka với `startingOffsets=latest`
2. Parse Debezium JSON: `get_json_object(value, '$.after')`
3. Lọc tombstones: `after IS NOT NULL`
4. Trích xuất fields bằng `from_json(after, schema)`
5. Thêm metadata: `ingestion_time`, `year`, `month`, `day`
6. Ghi vào Delta: `append` mode, phân vùng theo `year/month/day`
7. Checkpoint: `s3a://lakehouse/checkpoints/kafka_to_bronze`

### 3.2. Silver Layer (Curated + Features)

**Input:** Bronze Delta Lake (đọc incremental)

**Kiểm tra chất lượng dữ liệu:**

```python
# 1. Loại bỏ records không hợp lệ
df = df.filter(
    (col("trans_num").isNotNull()) &
    (col("cc_num").isNotNull()) &
    (col("trans_timestamp").isNotNull())
)

# 2. Điền thiếu cho fields quan trọng
df = df.fillna({
    "amt": 0.0,
    "is_fraud": 0
})
```

**Feature Engineering (40 features):**

**Geographic Features (2):**

```python
distance_km = haversine_distance(lat, long, merch_lat, merch_long)
is_distant_transaction = (distance_km > 50).cast("int")
```

**Demographic Features (2):**

```python
age = year(current_date()) - year(to_date(dob))
gender_encoded = when(col("gender") == "M", 1).otherwise(0)
```

**Time Features (6):**

```python
hour = hour(col("trans_timestamp"))
day_of_week = dayofweek(col("trans_timestamp"))
is_weekend = (day_of_week.isin(1, 7)).cast("int")
is_late_night = ((hour >= 22) | (hour <= 6)).cast("int")
hour_sin = sin(2 * pi * hour / 24)
hour_cos = cos(2 * pi * hour / 24)
```

**Amount Features (4):**

```python
log_amount = log1p(col("amt"))
amount_bin = when(amt < 50, 0).when(amt < 100, 1).when(amt < 200, 2).otherwise(3)
is_zero_amount = (amt == 0).cast("int")
is_high_amount = (amt > 1000).cast("int")
```

### 3.3. Gold Layer (Star Schema)

**Mô hình chiều:**

**1. dim_customer (Chiều khách hàng)**

```python
PK: customer_key (cc_num)
Thuộc tính: first_name, last_name, gender, age, dob, job
           customer_city, customer_state, customer_zip
           customer_lat, customer_long, customer_city_population
```

**2. dim_merchant (Chiều merchant)**

```python
PK: merchant_key (MD5 hash)
Thuộc tính: merchant_name, merchant_category
           merchant_lat, merchant_long
```

**3. dim_time (Chiều thời gian)**

```python
PK: time_key (định dạng yyyyMMddHH)
Thuộc tính: year, month, day, hour, minute
           day_of_week, week_of_year, quarter
           day_name, month_name, time_period, is_weekend
```

**4. dim_location (Chiều địa điểm)**

```python
PK: location_key (MD5 hash)
Thuộc tính: city, state, zip
           lat, long, city_pop
```

**5. fact_transactions (Fact giao dịch)**

```python
PK: transaction_key (trans_num)
Foreign Keys: customer_key, merchant_key, time_key
Measures: transaction_amount, is_fraud, distance_km
Risk Indicators: is_distant_transaction, is_late_night
                is_zero_amount, is_high_amount
```

---

## 4. MACHINE LEARNING PIPELINE

### 4.1. Kiến trúc Training Job

**File:** `spark/app/ml_training_job.py`  
**Thực thi:** Airflow DAG `model_retraining_taskflow` (hàng ngày 2 AM)  
**Nguồn dữ liệu:** Silver Delta Lake

**Pipeline huấn luyện:**

```python
# 1. Load dữ liệu
df = spark.read.format("delta").load("s3a://lakehouse/silver/transactions")

# 2. Chọn 20 features
features = [
    "amt", "log_amount", "is_zero_amount", "is_high_amount", "amount_bin",
    "distance_km", "is_distant_transaction", "lat", "long", "merch_lat", "merch_long", "city_pop",
    "age", "gender_encoded",
    "hour", "day_of_week", "is_weekend", "is_late_night", "hour_sin", "hour_cos"
]

# 3. Xử lý missing values
imputer = Imputer(strategy="median", inputCols=features, outputCols=features)
df = imputer.fit(df).transform(df)

# 4. Class balancing (1:1 ratio)
fraud_df = df.filter(col("is_fraud") == 1)
normal_df = df.filter(col("is_fraud") == 0)
fraud_count = fraud_df.count()
normal_df_balanced = normal_df.sample(fraction=fraud_count / normal_df.count(), seed=42)
balanced_df = fraud_df.union(normal_df_balanced)

# 5. Feature scaling (Min-Max)
assembler = VectorAssembler(inputCols=features, outputCol="features_raw")
scaler = MinMaxScaler(inputCol="features_raw", outputCol="features")
df_scaled = pipeline_prep.fit(balanced_df).transform(balanced_df)

# 6. Train/Test split (80/20)
train_df, test_df = df_scaled.randomSplit([0.8, 0.2], seed=42)

# 7. Train RandomForest
rf = RandomForestClassifier(
    featuresCol="features",
    labelCol="is_fraud",
    numTrees=200,
    maxDepth=30,
    seed=42
)
rf_model = rf.fit(train_df)

# 8. Evaluate
predictions = rf_model.transform(test_df)
metrics = {
    "accuracy": accuracy_evaluator.evaluate(predictions),
    "precision": precision_evaluator.evaluate(predictions),
    "recall": recall_evaluator.evaluate(predictions),
    "f1": f1_evaluator.evaluate(predictions),
    "auc": auc_evaluator.evaluate(predictions)
}

# 9. Log to MLflow
with mlflow.start_run(run_name=f"RandomForest_{timestamp}"):
    mlflow.log_params({"model_type": "RandomForest", "num_trees": 200})
    mlflow.log_metrics(metrics)
    mlflow.spark.log_model(rf_model, "model")
```

### 4.2. MLflow Integration

**Tracking Server:**

- URL: http://mlflow:5000
- Backend: PostgreSQL (`mlflow` db)
- Artifacts: MinIO S3 (`s3a://lakehouse/models/`)

**Experiment:**

- Tên: `fraud_detection_production`
- Runs: 2 mỗi chu kỳ (RandomForest + LogisticRegression)

### 4.3. Hiệu suất mong đợi

| Model              | Accuracy | Precision | Recall | F1     | AUC    |
| ------------------ | -------- | --------- | ------ | ------ | ------ |
| RandomForest       | ~96.8%   | ~95%      | ~98%   | ~96.5% | ~99.5% |
| LogisticRegression | ~85.3%   | ~80%      | ~90%   | ~85%   | ~92%   |

**Thời gian huấn luyện:**

- 50K records: ~2-3 phút
- 1M records: ~10-15 phút

### 4.4. FastAPI Model Integration

**Luồng hoạt động:**

```
MLflow Training (2 AM)
    ↓
Save model → MLflow Registry
    ↓
FastAPI /model/reload
    ↓
Load new model → Memory
    ↓
/predict endpoint → Use new model
```

**Code example - Tích hợp pipeline:**

```python
import requests

def predict_transaction(features):
    response = requests.post(
        "http://fraud-detection-api:8000/predict",
        json=features
    )
    return response.json()

# Real-time alert
result = predict_transaction(transaction_features)
if result["risk_level"] == "HIGH":
    send_alert(result["trans_num"], result["fraud_probability"])
```

---

## 5. TRIỂN KHAI & VẬN HÀNH

### 5.1. Docker Compose Services

**Tổng cộng:** 16 services

| Service             | Image           | Port       | Dependencies    |
| ------------------- | --------------- | ---------- | --------------- |
| postgres            | postgres:14     | 5432       | -               |
| kafka               | cp-kafka        | 9092       | zookeeper       |
| debezium            | debezium        | 8083       | kafka, postgres |
| minio               | minio           | 9000, 9001 | -               |
| spark-master        | custom-spark    | 7077, 8080 | minio           |
| spark-worker        | custom-spark    | -          | spark-master    |
| bronze-streaming    | custom-spark    | -          | kafka, spark    |
| hive-metastore      | custom-hive     | 9083       | metastore-db    |
| metastore-db        | postgres:14     | -          | -               |
| trino               | trino           | 8081, 8085 | hive-metastore  |
| mlflow              | mlflow          | 5000       | postgres, minio |
| airflow-webserver   | airflow         | 8081       | airflow-db      |
| airflow-scheduler   | airflow         | -          | airflow-db      |
| airflow-db          | postgres:14     | -          | -               |
| data-producer       | custom-producer | -          | postgres        |
| fraud-detection-api | custom-fastapi  | 8000       | mlflow, minio   |

### 5.2. Yêu cầu tài nguyên

**Môi trường Development:**

- CPU: 6 cores tối thiểu (8+ khuyến nghị)
- RAM: 10GB tối thiểu (16GB khuyến nghị)
- Disk: 30GB không gian trống
- Network: Internet ổn định cho Docker images

### 5.3. Monitoring & Observability

**Service UIs:**

- Spark Master: http://localhost:8080
- Airflow: http://localhost:8081
- Trino: http://localhost:8085
- MLflow: http://localhost:5000
- MinIO: http://localhost:9001
- Kafka UI: http://localhost:9002
- **FastAPI Docs: http://localhost:8000/docs**

### 5.4. Backup & Recovery

**Chiến lược Backup:**

```bash
# Backup MinIO bucket
docker exec minio mc mirror lakehouse /backup/lakehouse-$(date +%Y%m%d)

# Backup PostgreSQL
docker exec postgres pg_dump -U postgres frauddb > backup/frauddb.sql
```

---

## 6. TESTING & VALIDATION

### 6.1. Integration Tests

```bash
# End-to-end data flow
1. Insert test transaction → PostgreSQL
2. Verify CDC event → Kafka UI
3. Check Bronze Delta → MinIO
4. Trigger Silver job → Airflow
5. Verify features → Trino query
6. Trigger Gold job → Airflow
7. Verify star schema → Metabase
8. Test API prediction → FastAPI /predict
```

### 6.2. Performance Tests

```bash
# Throughput test
docker exec data-producer python producer.py --bulk-load 100000

# API performance
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d @test_transaction.json
# Mục tiêu: < 100ms response time
```

---

## 7. HẠN CHẾ & CÔNG VIỆC TƯƠNG LAI

### 7.1. Hạn chế hiện tại

1. **Single-node Spark**: Không scale horizontally
2. **Chatbot chưa implement**: LangChain query interface chưa có
3. **No alerting system**: Fraud alerts chưa tự động
4. **Limited data retention**: Kafka 7 ngày, Delta vacuum 30 ngày

### 7.2. Cải tiến tương lai

1. **Multi-node Spark cluster** (Kubernetes)
2. **Chatbot interface** (Streamlit + LangChain + Trino)
3. **Alert system** (Kafka Connect + Email/Slack)
4. **Advanced ML** (XGBoost, Deep Learning, AutoML)
5. **Data quality monitoring** (Great Expectations)
6. **CI/CD pipeline** (GitHub Actions)
7. **Grafana monitoring** (Prometheus + Grafana)

---

## 8. TÀI LIỆU THAM KHẢO

### 8.1. Documentation

- Delta Lake: https://docs.delta.io/
- Apache Spark: https://spark.apache.org/docs/
- Trino: https://trino.io/docs/
- Apache Airflow: https://airflow.apache.org/docs/
- MLflow: https://mlflow.org/docs/
- FastAPI: https://fastapi.tiangolo.com/

### 8.2. Dataset

- Sparkov Dataset: https://www.kaggle.com/datasets/kartik2112/fraud-detection
- Kaggle Notebook: https://www.kaggle.com/code/kartik2112/fraud-detection

### 8.3. Project Repository

- GitHub: https://github.com/bin-bard/real-time-fraud-detection-lakehouse
- Documentation: `docs/` folder
- Issues: GitHub Issues tracker

---

**Phiên bản tài liệu:** 6.0  
**Cập nhật lần cuối:** 4 tháng 12, 2025  
**Trạng thái:** ✅ Sẵn sàng Production
