# ĐẶC TẢ KỸ THUẬT DỰ ÁN (PROJECT SPECIFICATION)

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
4. **ML Training**: Automated model retraining qua Airflow
5. **Interactive Analytics**: Trino query engine + Metabase dashboard

### 1.2. Phạm vi dữ liệu

- **Dataset**: Sparkov Credit Card Transactions (Kaggle)
- **Thời gian**: 01/2019 - 12/2020 (1.8M transactions)
- **Fraud rate**: 0.5-1% (real-world imbalance)
- **Streaming mode**: Mô phỏng real-time với checkpoint recovery

---

## 2. KIẾN TRÚC HỆ THỐNG

### 2.1. Tổng quan Architecture

```
┌──────────────────────────────────────────────────────────────┐
│ Layer 1: Data Ingestion (CDC Pipeline)                      │
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
│ Spark Structured Streaming (Continuous)                      │
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
│ Spark Batch Job (Airflow - Every 5 minutes)                 │
│ Input: Bronze Delta Lake (incremental read)                 │
│ Processing:                                                  │
│   - Data quality checks (drop nulls, fill missing)          │
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
│ Spark Batch Job (Airflow - Every 5 minutes)                 │
│ Input: Silver Delta Lake                                     │
│ Processing: Dimensional modeling                             │
│ Output: 5 Delta tables                                       │
│   - dim_customer (Customer dimension)                        │
│   - dim_merchant (Merchant dimension)                        │
│   - dim_time (Time dimension)                                │
│   - dim_location (Location dimension)                        │
│   - fact_transactions (Transaction facts)                    │
└──────────────────────────────────────────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────────┐
│ Layer 5: Query & Consumption                                │
├──────────────────────────────────────────────────────────────┤
│ Trino Query Engine (Port 8085)                              │
│   ├─ Delta Catalog (Primary): Query data từ _delta_log/     │
│   └─ Hive Catalog (Optional): Metadata cache for SHOW TABLES│
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
│ Layer 6: ML & Orchestration                                 │
├──────────────────────────────────────────────────────────────┤
│ Apache Airflow 2.8.0 (Workflow Orchestration)               │
│   DAG 1: lakehouse_pipeline_taskflow (Every 5 min)          │
│     - run_silver_transformation                              │
│     - run_gold_transformation                                │
│   DAG 2: model_retraining_taskflow (Daily 2 AM)             │
│     - train_ml_models (RandomForest + LogisticRegression)    │
│                                                              │
│ MLflow 2.8.0 (Model Tracking)                               │
│   - Experiment: fraud_detection_production                   │
│   - Artifacts: s3a://lakehouse/models/                       │
│   - Metrics: accuracy, precision, recall, F1, AUC            │
└──────────────────────────────────────────────────────────────┘
```

### 2.2. Component Details

#### 2.2.1. Data Ingestion Layer

**PostgreSQL 14 (Source Database)**

- Role: OLTP database mô phỏng production system
- Schema: 22 columns (transaction data)
- CDC Config: `wal_level=logical`, `max_replication_slots=4`
- Checkpoint Table: `producer_checkpoint` (track data producer progress)

**Debezium 2.5 (CDC Connector)**

- Mode: PostgreSQL connector với Kafka Connect
- Capture: INSERT operations (UPDATE/DELETE optional)
- Format: Debezium JSON with `after` field
- Special Config: `decimal.handling.mode=double` (fix NUMERIC encoding)
- Topic: `postgres.public.transactions`

**Apache Kafka**

- Broker: Single node (dev environment)
- Partitions: 3 (for parallel processing)
- Retention: 7 days
- UI: Kafka UI on port 9002

#### 2.2.2. Storage Layer

**MinIO (S3-Compatible Object Storage)**

- Bucket: `lakehouse`
- Structure:
  - `/bronze/transactions/` - Raw CDC data
  - `/silver/transactions/` - Feature engineered data
  - `/gold/dim_*/` - Dimension tables
  - `/gold/fact_*/` - Fact tables
  - `/checkpoints/` - Spark streaming checkpoints
  - `/models/` - MLflow artifacts
- Access: `minio` / `minio123`
- Endpoint: http://minio:9000

**Delta Lake 2.4.0**

- Format: Parquet + Transaction Log (`_delta_log/`)
- Features:
  - ACID transactions
  - Time travel (version history)
  - Schema evolution
  - Audit logging
  - Compaction (OPTIMIZE command)
  - Vacuum (retention period)
- Partition Strategy:
  - Bronze/Silver: `year/month/day`
  - Gold: Không partition (small dimensions)

**Hive Metastore 3.1.3 (Optional Metadata Cache)**

- Database: PostgreSQL (`metastore` db)
- Purpose: Metadata cache cho Trino
- Performance: SHOW TABLES ~100ms (vs ~1-2s direct S3 scan)
- **KHÔNG dùng để query data** - chỉ cache schema info
- Auto-registration: `register_tables_to_hive.py` (manual trigger)

#### 2.2.3. Processing Layer

**Apache Spark 3.4.1**

- Mode: Spark Standalone Cluster
- Components:
  - 1 Master node (resource manager)
  - 1 Worker node (executor)
- Configuration:
  - `spark.sql.extensions=io.delta.sql.DeltaSparkSessionExtension`
  - `spark.sql.catalog.spark_catalog=org.apache.spark.sql.delta.catalog.DeltaCatalog`
  - S3A credentials: `minio` / `minio123`
  - Delta Lake JARs: pre-installed in custom image

**Processing Jobs:**

1. **Bronze Streaming** (`streaming_job.py`)
   - Mode: Continuous streaming
   - Trigger: `availableNow=False` (continuous)
   - CPU: ~195% (normal for streaming)
   - Auto-start: Docker compose `depends_on`

2. **Silver Batch** (`silver_job.py`)
   - Mode: Batch ETL
   - Trigger: Airflow every 5 minutes
   - Processing: Incremental (watermark-based)
   - CPU: 0% during sleep, spike when running

3. **Gold Batch** (`gold_job.py`)
   - Mode: Batch ETL
   - Trigger: Airflow every 5 minutes after Silver
   - Processing: Star schema transformation
   - Output: 5 Delta tables

4. **ML Training** (`ml_training_job.py`)
   - Mode: Batch ML
   - Trigger: Airflow daily 2 AM
   - Models: RandomForest + LogisticRegression
   - Tracking: MLflow experiment

#### 2.2.4. Query Layer

**Trino (Query Engine)**

- Version: Latest stable
- Port: 8081 (internal), 8085 (external)
- Catalogs:
  - **`delta`** - Primary catalog (query data)
  - **`hive`** - Metadata cache (list tables only)
- Memory: 2GB heap (configurable)
- Parallelism: 4 workers

**Query Pattern:**

```sql
-- ✅ ĐÚNG - Query data qua Delta catalog
SELECT * FROM delta.gold.fact_transactions;

-- ✅ OK - List tables qua Hive cache
SHOW TABLES FROM hive.gold;

-- ❌ SAI - Query data qua Hive (không hỗ trợ Delta format)
-- SELECT * FROM hive.gold.fact_transactions; -- Error!
```

#### 2.2.5. Orchestration Layer

**Apache Airflow 2.8.0**

- Mode: Docker Compose deployment
- Components:
  - Webserver: UI on port 8081
  - Scheduler: Task execution
  - Database: PostgreSQL (`airflow` db)
  - Executor: LocalExecutor
- Auth: `admin` / `admin`

**DAGs:**

1. `lakehouse_pipeline_taskflow` (Every 5 minutes)
   - check_bronze_data
   - run_silver_transformation
   - run_gold_transformation
   - verify_trino
   - send_pipeline_summary

2. `model_retraining_taskflow` (Daily 2 AM)
   - check_data_availability
   - train_ml_models
   - verify_mlflow
   - send_notification

---

## 3. DATA SCHEMA & PROCESSING

### 3.1. Bronze Layer (Raw CDC)

**Source:** Kafka topic `postgres.public.transactions`

**Schema Definition (22 columns):**

```python
schema = StructType([
    StructField("trans_date_trans_time", StringType()),  # Parse later
    StructField("cc_num", StringType()),                 # Cast to LongType
    StructField("merchant", StringType()),
    StructField("category", StringType()),
    StructField("amt", DoubleType()),                    # ⚠️ From Debezium double
    StructField("first", StringType()),
    StructField("last", StringType()),
    StructField("gender", StringType()),
    StructField("street", StringType()),
    StructField("city", StringType()),
    StructField("state", StringType()),
    StructField("zip", StringType()),
    StructField("lat", DoubleType()),
    StructField("long", DoubleType()),
    StructField("city_pop", StringType()),               # Cast to IntegerType
    StructField("job", StringType()),
    StructField("dob", StringType()),                    # Parse to DateType
    StructField("trans_num", StringType()),
    StructField("unix_time", StringType()),              # Cast to LongType
    StructField("merch_lat", DoubleType()),
    StructField("merch_long", DoubleType()),
    StructField("is_fraud", StringType())                # Cast to IntegerType
])
```

**Processing Logic:**

1. Read from Kafka with `startingOffsets=latest`
2. Parse Debezium JSON: `get_json_object(value, '$.after')`
3. Filter tombstones: `after IS NOT NULL`
4. Extract fields using `from_json(after, schema)`
5. Add metadata: `ingestion_time`, `year`, `month`, `day`
6. Write to Delta: `append` mode, partitioned by `year/month/day`
7. Checkpoint: `s3a://lakehouse/checkpoints/kafka_to_bronze`

**Special Handling:**

- `amt` field: Debezium sends as JSON double (not Base64)
  - Connector config: `decimal.handling.mode=double`
  - No need to decode - direct DoubleType parsing

### 3.2. Silver Layer (Curated + Features)

**Input:** Bronze Delta Lake (incremental read)

**Data Quality Checks:**

```python
# 1. Drop invalid records
df = df.filter(
    (col("trans_num").isNotNull()) &
    (col("cc_num").isNotNull()) &
    (col("trans_timestamp").isNotNull())
)

# 2. Fill missing critical fields
df = df.fillna({
    "amt": 0.0,           # Zero-amount transaction
    "is_fraud": 0         # Assume normal
})

# 3. Keep semantic nulls (có ý nghĩa)
# lat, long, merch_lat, merch_long: NULL = "no location info"
# → Xử lý trong feature engineering
```

**Feature Engineering (40 features):**

**Geographic Features (2):**

```python
# Haversine distance (km)
distance_km = haversine_distance(lat, long, merch_lat, merch_long)
  # Fill -1 if any coordinate is NULL

# Distant transaction flag
is_distant_transaction = (distance_km > 50).cast("int")
```

**Demographic Features (2):**

```python
# Age calculation
age = year(current_date()) - year(to_date(dob))
  # Fill -1 if dob is NULL

# Gender encoding
gender_encoded = when(col("gender") == "M", 1).otherwise(0)
  # NULL → 0 (default female)
```

**Time Features (6):**

```python
# Extract time components
hour = hour(col("trans_timestamp"))
day_of_week = dayofweek(col("trans_timestamp"))  # 1=Sun, 7=Sat
is_weekend = (day_of_week.isin(1, 7)).cast("int")
is_late_night = ((hour >= 22) | (hour <= 6)).cast("int")

# Cyclic encoding (preserve circular nature)
hour_sin = sin(2 * pi * hour / 24)
hour_cos = cos(2 * pi * hour / 24)
```

**Amount Features (4):**

```python
# Log transformation (handle zero)
log_amount = log1p(col("amt"))  # log(1 + amt)

# Binning
amount_bin = when(amt < 50, 0)
           .when(amt < 100, 1)
           .when(amt < 200, 2)
           .otherwise(3)

# Flags
is_zero_amount = (amt == 0).cast("int")
is_high_amount = (amt > 1000).cast("int")
```

**Original Features (26):** Preserve all Bronze columns

**Output:** 40 total features

**Partition:** `year/month/day` (same as Bronze)

**Write Mode:** `append` (incremental)

### 3.3. Gold Layer (Star Schema)

**Dimensional Model:**

**1. dim_customer**

```python
PK: customer_key (cc_num)
Attributes:
  - first_name, last_name, gender, age, dob, job
  - customer_city, customer_state, customer_zip
  - customer_lat, customer_long
  - customer_city_population
  - last_updated
```

**2. dim_merchant**

```python
PK: merchant_key (MD5 hash)
Attributes:
  - merchant_name
  - merchant_category
  - merchant_lat, merchant_long
  - last_updated
```

**3. dim_time**

```python
PK: time_key (yyyyMMddHH format)
Attributes:
  - year, month, day, hour, minute
  - day_of_week, week_of_year, quarter
  - day_name, month_name
  - time_period (Morning/Afternoon/Evening/Night)
  - is_weekend
```

**4. dim_location**

```python
PK: location_key (MD5 hash)
Attributes:
  - city, state, zip
  - lat, long
  - city_pop
  - last_updated
```

**5. fact_transactions**

```python
PK: transaction_key (trans_num)
Foreign Keys:
  - customer_key → dim_customer
  - merchant_key → dim_merchant
  - time_key → dim_time

Measures:
  - transaction_amount
  - is_fraud (ground truth)
  - fraud_prediction (from ML model - optional)
  - distance_km
  - log_amount, amount_bin

Degenerate Dimensions:
  - transaction_timestamp
  - transaction_category
  - unix_time

Risk Indicators:
  - is_distant_transaction
  - is_late_night
  - is_zero_amount
  - is_high_amount

Time Features:
  - transaction_hour, transaction_day_of_week
  - is_weekend_transaction
  - hour_sin, hour_cos

Metadata:
  - ingestion_time
  - fact_created_time
```

**Processing Logic:**

```python
# 1. Extract unique dimensions (dedup)
dim_customer = silver_df.select(customer_cols).dropDuplicates(["cc_num"])
dim_merchant = silver_df.select(merchant_cols).dropDuplicates(["merchant", "merch_lat", "merch_long"])
dim_time = silver_df.select(time_cols).dropDuplicates(["time_key"])
dim_location = silver_df.select(location_cols).dropDuplicates(["city", "state", "zip"])

# 2. Create fact table with foreign keys
fact_transactions = silver_df \
    .join(dim_customer, on="cc_num") \
    .join(dim_merchant, on=["merchant", "merch_lat", "merch_long"]) \
    .join(dim_time, on="time_key") \
    .select(fact_cols)

# 3. Write to Delta (merge mode for dimensions, append for facts)
dim_customer.write.mode("overwrite").save("s3a://lakehouse/gold/dim_customer")
fact_transactions.write.mode("append").save("s3a://lakehouse/gold/fact_transactions")
```

---

## 4. MACHINE LEARNING PIPELINE

### 4.1. Training Job Architecture

**File:** `spark/app/ml_training_job.py`

**Execution:** Airflow DAG `model_retraining_taskflow` (daily 2 AM)

**Data Source:** Silver Delta Lake

**Training Pipeline:**

```python
# 1. Load data
df = spark.read.format("delta").load("s3a://lakehouse/silver/transactions")

# 2. Filter valid amounts
df = df.filter(col("amt") > 0)  # Remove zero-amount transactions

# 3. Feature selection (20 features)
features = [
    # Amount
    "amt", "log_amount", "is_zero_amount", "is_high_amount", "amount_bin",
    # Geographic
    "distance_km", "is_distant_transaction", "lat", "long", "merch_lat", "merch_long", "city_pop",
    # Demographic
    "age", "gender_encoded",
    # Time
    "hour", "day_of_week", "is_weekend", "is_late_night", "hour_sin", "hour_cos"
]

# 4. Handle missing values
from pyspark.ml.feature import Imputer
imputer = Imputer(strategy="median", inputCols=features, outputCols=features)
df = imputer.fit(df).transform(df)

# 5. Class balancing (Undersample majority)
fraud_df = df.filter(col("is_fraud") == 1)
normal_df = df.filter(col("is_fraud") == 0)
fraud_count = fraud_df.count()
normal_df_balanced = normal_df.sample(fraction=fraud_count / normal_df.count(), seed=42)
balanced_df = fraud_df.union(normal_df_balanced)

# 6. Feature scaling
from pyspark.ml.feature import MinMaxScaler, VectorAssembler
assembler = VectorAssembler(inputCols=features, outputCol="features_raw")
scaler = MinMaxScaler(inputCol="features_raw", outputCol="features")
pipeline_prep = Pipeline(stages=[assembler, scaler])
df_scaled = pipeline_prep.fit(balanced_df).transform(balanced_df)

# 7. Train/Test split
train_df, test_df = df_scaled.randomSplit([0.8, 0.2], seed=42)

# 8. Train models
from pyspark.ml.classification import RandomForestClassifier, LogisticRegression

rf = RandomForestClassifier(
    featuresCol="features",
    labelCol="is_fraud",
    numTrees=200,
    maxDepth=30,
    seed=42
)

lr = LogisticRegression(
    featuresCol="features",
    labelCol="is_fraud",
    maxIter=1000,
    regParam=0.0
)

rf_model = rf.fit(train_df)
lr_model = lr.fit(train_df)

# 9. Evaluate
from pyspark.ml.evaluation import BinaryClassificationEvaluator, MulticlassClassificationEvaluator

predictions_rf = rf_model.transform(test_df)
predictions_lr = lr_model.transform(test_df)

# Metrics
metrics = {
    "accuracy": accuracy_evaluator.evaluate(predictions),
    "precision": precision_evaluator.evaluate(predictions),
    "recall": recall_evaluator.evaluate(predictions),
    "f1": f1_evaluator.evaluate(predictions),
    "auc": auc_evaluator.evaluate(predictions)
}

# Confusion matrix
tp = predictions.filter((col("is_fraud") == 1) & (col("prediction") == 1)).count()
tn = predictions.filter((col("is_fraud") == 0) & (col("prediction") == 0)).count()
fp = predictions.filter((col("is_fraud") == 0) & (col("prediction") == 1)).count()
fn = predictions.filter((col("is_fraud") == 1) & (col("prediction") == 0)).count()

# 10. Log to MLflow
import mlflow
mlflow.set_tracking_uri("http://mlflow:5000")
mlflow.set_experiment("fraud_detection_production")

with mlflow.start_run(run_name=f"RandomForest_{timestamp}"):
    mlflow.log_params({
        "model_type": "RandomForest",
        "num_trees": 200,
        "max_depth": 30,
        "train_samples": train_df.count(),
        "test_samples": test_df.count()
    })
    mlflow.log_metrics(metrics)
    mlflow.log_metrics({"tp": tp, "tn": tn, "fp": fp, "fn": fn})
    mlflow.spark.log_model(
        rf_model,
        "model",
        registered_model_name="fraud_detection_randomforest"
    )
```

### 4.2. MLflow Integration

**Tracking Server:**

- URL: http://mlflow:5000
- Backend: PostgreSQL (`mlflow` db)
- Artifacts: MinIO S3 (`s3a://lakehouse/models/`)

**Experiment:**

- Name: `fraud_detection_production`
- Runs: 2 per training cycle (RandomForest + LogisticRegression)

**Logged Artifacts:**

- Model binary (Spark MLlib format)
- Feature importance (RandomForest)
- Training logs (stdout)

**Environment Variables (S3 access):**

```bash
AWS_ACCESS_KEY_ID=minio
AWS_SECRET_ACCESS_KEY=minio123
MLFLOW_S3_ENDPOINT_URL=http://minio:9000
```

### 4.3. Expected Performance

**Based on Kaggle benchmark:**

| Model              | Accuracy | Precision | Recall | F1    | AUC   |
| ------------------ | -------- | --------- | ------ | ----- | ----- |
| RandomForest       | ~96.8%   | ~95%      | ~98%   | ~96.5%| ~99.5%|
| LogisticRegression | ~85.3%   | ~80%      | ~90%   | ~85%  | ~92%  |

**Training Time:**

- With 50K records: ~2-3 minutes
- With 1M records: ~10-15 minutes

---

## 5. DEPLOYMENT & OPERATIONS

### 5.1. Docker Compose Services

**Total:** 15 services

| Service              | Image                    | Port       | Dependencies                   |
| -------------------- | ------------------------ | ---------- | ------------------------------ |
| postgres             | postgres:14              | 5432       | -                              |
| kafka                | cp-kafka                 | 9092       | zookeeper                      |
| debezium             | debezium/connect         | 8083       | kafka, postgres                |
| minio                | minio/minio              | 9000, 9001 | -                              |
| spark-master         | custom-spark             | 7077, 8080 | minio                          |
| spark-worker         | custom-spark             | -          | spark-master                   |
| bronze-streaming     | custom-spark             | -          | kafka, spark-master            |
| hive-metastore       | custom-hive              | 9083       | metastore-db, minio            |
| metastore-db         | postgres:14              | -          | -                              |
| trino                | trinodb/trino            | 8081, 8085 | hive-metastore, minio          |
| mlflow               | mlflow/mlflow            | 5000       | postgres, minio                |
| airflow-webserver    | apache/airflow           | 8081       | airflow-db                     |
| airflow-scheduler    | apache/airflow           | -          | airflow-db                     |
| airflow-db           | postgres:14              | -          | -                              |
| data-producer        | custom-producer          | -          | postgres                       |

### 5.2. Resource Requirements

**Development Environment:**

- CPU: 6 cores minimum (8+ recommended)
- RAM: 10GB minimum (16GB recommended)
- Disk: 30GB free space
- Network: Stable internet for Docker images

**Production Scaling (future):**

- Kafka: 3 brokers (HA)
- Spark: 3+ workers (horizontal scaling)
- MinIO: Distributed mode (4+ nodes)
- Trino: Separate coordinator + workers

### 5.3. Monitoring & Observability

**Service UIs:**

- Spark Master: http://localhost:8080
- Airflow: http://localhost:8081
- Trino: http://localhost:8085
- MLflow: http://localhost:5000
- MinIO: http://localhost:9001
- Kafka UI: http://localhost:9002

**Log Aggregation:**

```bash
# Centralized logs
docker logs <service-name> --tail 100 --follow

# Filter by keyword
docker logs bronze-streaming | grep "ERROR"

# Export logs
docker logs airflow-scheduler > logs/airflow.log
```

**Metrics:**

```bash
# Resource usage
docker stats --no-stream

# Specific service
docker stats bronze-streaming spark-master --no-stream
```

### 5.4. Backup & Recovery

**Data Persistence:**

- MinIO data: `/data` volume
- PostgreSQL data: Named volumes (`postgres_data`, `airflow_db`, etc.)
- Spark checkpoints: MinIO bucket

**Backup Strategy:**

```bash
# Backup MinIO bucket
docker exec minio mc mirror lakehouse /backup/lakehouse-$(date +%Y%m%d)

# Backup Postgres
docker exec postgres pg_dump -U postgres frauddb > backup/frauddb.sql

# Backup Airflow metadata
docker exec airflow-db pg_dump -U airflow airflow > backup/airflow.sql
```

**Disaster Recovery:**

```bash
# Reset and restore
docker compose down -v
docker compose up -d
# Wait for services ready
docker exec minio mc cp -r /backup/lakehouse-20241204 lakehouse/
docker exec postgres psql -U postgres < backup/frauddb.sql
```

---

## 6. TESTING & VALIDATION

### 6.1. Unit Tests

```bash
# Test Bronze streaming job
docker exec bronze-streaming pytest /app/tests/test_streaming.py

# Test Silver transformation
docker exec spark-master spark-submit --py-files /app/tests/test_silver.py

# Test Gold dimensional model
docker exec spark-master spark-submit --py-files /app/tests/test_gold.py
```

### 6.2. Integration Tests

```bash
# End-to-end data flow
1. Insert test transaction → PostgreSQL
2. Verify CDC event → Kafka UI
3. Check Bronze Delta → MinIO
4. Trigger Silver job → Airflow
5. Verify features → Trino query
6. Trigger Gold job → Airflow
7. Verify star schema → Metabase
```

### 6.3. Performance Tests

```bash
# Throughput test
docker exec data-producer python producer.py --bulk-load 100000
# Measure: Time to process 100K records

# Query performance
docker exec trino trino --server localhost:8081 --execute "
  SELECT COUNT(*) FROM delta.gold.fact_transactions
  WHERE transaction_timestamp > current_timestamp - INTERVAL '1' HOUR
"
# Target: < 5 seconds
```

---

## 7. KNOWN LIMITATIONS & FUTURE WORK

### 7.1. Current Limitations

1. **Single-node Spark**: Không scale horizontally
2. **No real-time ML inference**: Prediction qua API chưa implement
3. **Chatbot missing**: LangChain query interface chưa có
4. **No alerting**: Fraud alerts chưa tự động
5. **Limited data retention**: Kafka 7 days, Delta vacuum 30 days

### 7.2. Future Enhancements

1. **Multi-node Spark cluster** (Kubernetes)
2. **Real-time scoring** (FastAPI + MLflow model serving)
3. **Chatbot** (Streamlit + LangChain + Trino)
4. **Alert system** (Kafka Connect + Email/Slack)
5. **Advanced ML** (Deep Learning, AutoML)
6. **Data quality** (Great Expectations)
7. **CI/CD pipeline** (GitHub Actions)

---

## 8. REFERENCES

### 8.1. Documentation

- Delta Lake: https://docs.delta.io/
- Apache Spark: https://spark.apache.org/docs/
- Trino: https://trino.io/docs/
- Apache Airflow: https://airflow.apache.org/docs/
- MLflow: https://mlflow.org/docs/

### 8.2. Dataset

- Sparkov Dataset: https://www.kaggle.com/datasets/kartik2112/fraud-detection
- Kaggle Notebook: https://www.kaggle.com/code/kartik2112/fraud-detection

### 8.3. Project Repository

- GitHub: https://github.com/bin-bard/real-time-fraud-detection-lakehouse
- Documentation: `docs/` folder
- Issues: GitHub Issues tracker

---

**Document Version:** 6.0  
**Last Updated:** December 4, 2025  
**Status:** ✅ Production Ready
