# Real-Time Fraud Detection Data Lakehouse

Hệ thống Data Lakehouse phát hiện gian lận thẻ tín dụng trong thời gian thực sử dụng **Sparkov Credit Card Transactions Dataset** với kiến trúc Medallion (Bronze-Silver-Gold).

![Architecture Diagram](docs/architecture.png)

## Tổng quan

Dự án xây dựng pipeline xử lý dữ liệu end-to-end:

1. **Thu thập dữ liệu**: PostgreSQL → Debezium CDC → Kafka (real-time streaming)
2. **Xử lý dữ liệu**: Apache Spark với Delta Lake (Bronze/Silver/Gold layers)
3. **Feature Engineering**: 15 features từ dữ liệu địa lý, nhân khẩu học, giao dịch
4. **Machine Learning**: Random Forest & Logistic Regression (99%+ accuracy)
5. **Model Serving**: FastAPI cho prediction real-time

## Tech Stack

| Component         | Technology               | Mô tả                          |
| ----------------- | ------------------------ | ------------------------------ |
| **Source DB**     | PostgreSQL 14            | OLTP database với CDC enabled  |
| **CDC**           | Debezium 2.5             | Change Data Capture connector  |
| **Streaming**     | Apache Kafka             | Message broker                 |
| **Processing**    | Apache Spark 3.4.1       | Stream & batch processing      |
| **Storage**       | Delta Lake 2.4.0 + MinIO | ACID transactions, time travel |
| **Metastore**     | Hive Metastore           | Table metadata management      |
| **ML**            | Scikit-learn, MLflow     | Model training & registry      |
| **API**           | FastAPI                  | Real-time prediction service   |
| **Orchestration** | Apache Airflow           | Workflow scheduling            |

## Cấu trúc thư mục

```
real-time-fraud-detection-lakehouse/
├── airflow/dags/              # Airflow DAGs (model retraining, reports)
├── config/                    # Service configurations
│   ├── metastore/             # Hive metastore config
│   ├── spark/                 # Spark defaults
│   └── trino/                 # Trino settings
├── data/                      # Sparkov dataset (CSV files)
├── database/                  # PostgreSQL initialization
│   └── init_postgres.sql      # Schema setup (22 columns)
├── deployment/                # Infrastructure automation
│   ├── debezium/              # CDC configuration scripts
│   └── minio/                 # MinIO bucket setup
├── docs/                      # Documentation
│   └── PROJECT_SPECIFICATION.md
├── notebooks/                 # Jupyter notebooks (EDA, experiments)
├── services/                  # Microservices
│   ├── data-producer/         # PostgreSQL data simulator
│   ├── fraud-detection-api/   # FastAPI prediction service
│   └── mlflow/                # MLflow tracking server
├── spark/                     # Custom Spark with ML libraries
│   ├── app/                   # PySpark jobs
│   │   ├── streaming_job.py   # Bronze layer (CDC → Delta Lake)
│   │   ├── silver_layer_job.py # Feature engineering (15 features)
│   │   ├── gold_layer_dimfact_job.py # Star Schema (dimensions/facts)
│   │   └── ml_training_job.py # Model training pipeline
│   └── Dockerfile             # Spark + MLflow + ML libraries
├── sql/                       # SQL views for Gold layer
│   └── gold_layer_views.sql   # Materialized views for dashboards
├── docker-compose.yml         # 11 services orchestration
└── README.md
```

## Dataset

**Sparkov Credit Card Transactions Fraud Detection Dataset** ([Kaggle](https://www.kaggle.com/datasets/kartik2112/fraud-detection))

- `data/fraudTrain.csv` - 1,296,675 transactions (01/2019 - 12/2020)
- `data/fraudTest.csv` - 555,719 transactions
- **22 columns**: Geographic (lat/long), demographic (age, gender, job), transaction (amount, merchant, category)

### Schema chính

| Column                    | Type     | Description                  |
| ------------------------- | -------- | ---------------------------- |
| `trans_date_trans_time`   | DateTime | Thời gian giao dịch          |
| `cc_num`                  | Long     | Số thẻ tín dụng              |
| `merchant`                | String   | Tên cửa hàng                 |
| `category`                | String   | Danh mục (grocery, gas, ...) |
| `amt`                     | Double   | Số tiền giao dịch            |
| `gender`                  | String   | Giới tính (M/F)              |
| `lat`, `long`             | Double   | Vị trí khách hàng            |
| `merch_lat`, `merch_long` | Double   | Vị trí cửa hàng              |
| `is_fraud`                | Integer  | Nhãn gian lận (0/1)          |

### Feature Engineering (15 features)

**Geographic**: `distance_km` (Haversine), `is_distant_transaction`
**Demographic**: `age`, `gender_encoded`
**Time**: `hour`, `day_of_week`, `is_weekend`, `is_late_night`, `hour_sin`, `hour_cos`
**Amount**: `log_amount`, `amount_bin`, `is_zero_amount`, `is_high_amount`

## Hướng dẫn chạy

### 1. Yêu cầu hệ thống

- Docker & Docker Compose
- Python 3.9+
- 8GB RAM, 20GB disk space

---

### 2. Khởi động hệ thống

#### Cách 1: Tự động (Khuyến nghị)

```bash
# Clone repository
git clone https://github.com/bin-bard/real-time-fraud-detection-lakehouse.git
cd real-time-fraud-detection-lakehouse

# Khởi động toàn bộ hệ thống (MinIO buckets, Debezium CDC connector, data-producer đều tự động)
docker-compose up -d
```

> **Lưu ý:** Không cần chạy thêm bất kỳ lệnh setup nào khác.

#### Cách 2: Thủ công (tùy chỉnh từng bước)

```bash
# Clone repository
git clone https://github.com/bin-bard/real-time-fraud-detection-lakehouse.git
cd real-time-fraud-detection-lakehouse

# Khởi động các service chính (không tự động tạo bucket, không tự động chạy data-producer)
docker-compose up -d --scale minio-setup=0 --scale data-producer=0

# Tạo MinIO buckets thủ công
docker-compose run --rm minio-setup

# Setup Debezium CDC (PowerShell)
.\deployment\debezium\setup_debezium.ps1

# Khởi động data-producer thủ công (nếu muốn)
docker-compose up -d data-producer
```

#### Rebuild MLflow service (nếu gặp lỗi)

```powershell
# Rebuild MLflow với cấu trúc mới
docker-compose build mlflow
docker-compose up -d mlflow

# Kiểm tra MLflow logs
docker logs mlflow -f
```

---

### 3. Chạy Data Pipeline (Streaming Architecture)

Hệ thống sử dụng **kiến trúc streaming liên tục** - khi dữ liệu vào Bronze thì tự động được xử lý qua Silver và Gold ngay lập tức.

#### ⚡ **Cách 1: Tự động 100% (Khuyến nghị)**

```bash
# Chỉ cần 1 lệnh duy nhất - Tất cả tự động!
docker-compose up -d
```

✅ **3 streaming jobs sẽ tự động khởi động:**
- `bronze-streaming`: Kafka → Bronze Delta Lake
- `silver-streaming`: Bronze → Silver (15 features)
- `gold-streaming`: Silver → Gold (Star Schema)

**Kiểm tra logs:**
```bash
# Xem tất cả streaming jobs
docker-compose logs -f bronze-streaming silver-streaming gold-streaming

# Hoặc từng job riêng lẻ
docker logs -f bronze-streaming
docker logs -f silver-streaming
docker logs -f gold-streaming
```

---

#### 🚀 **Cách 2: Script PowerShell (Mở 3 terminals riêng)**

```powershell
# Chạy script tự động (mở 3 cửa sổ riêng cho mỗi job)
.\scripts\start-streaming-pipeline.ps1
```

**Ưu điểm:** Dễ debug, có thể Ctrl+C từng job riêng

---

#### 🔧 **Cách 3: Thủ công (Chỉ khi cần debug chi tiết)**

**Bước 1: Bronze Layer (CDC ingestion)**

Mở terminal đầu tiên và chạy Bronze streaming job:

```bash
docker exec spark-master /opt/spark/bin/spark-submit \
  --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.4.1,io.delta:delta-core_2.12:2.4.0,org.apache.hadoop:hadoop-aws:3.3.4 \
  --conf 'spark.sql.extensions=io.delta.sql.DeltaSparkSessionExtension' \
  --conf 'spark.sql.catalog.spark_catalog=org.apache.spark.sql.delta.catalog.DeltaCatalog' \
  /app/streaming_job.py
```

**Kết quả mong đợi:**
```
✅ Spark Session with Delta Lake created successfully.
Bronze layer streaming started. Writing to MinIO...
Writing batch 0 to Bronze layer...
Batch 0 written to Bronze successfully.
```

**Không tắt terminal này** - để job chạy liên tục. Chờ thấy ít nhất 5 batches thành công trước khi chạy Silver job.

**Bước 2: Silver Layer (Feature engineering) - Streaming Mode**

Mở terminal mới và chạy:

```bash
docker exec -it spark-master bash -c "/opt/spark/bin/spark-submit \
  --packages io.delta:delta-core_2.12:2.4.0,org.apache.hadoop:hadoop-aws:3.3.4 \
  --conf 'spark.sql.extensions=io.delta.sql.DeltaSparkSessionExtension' \
  --conf 'spark.sql.catalog.spark_catalog=org.apache.spark.sql.delta.catalog.DeltaCatalog' \
  /app/silver_layer_job.py"
```

**Kết quả:**
- Job sẽ chạy liên tục, tự động xử lý dữ liệu mới từ Bronze
- Checkpoint được lưu tại `s3a://lakehouse/checkpoints/bronze_to_silver`
- Trigger mỗi 30 giây để xử lý micro-batch
- **Không tắt terminal này** - để job chạy liên tục

**Bước 3: Gold Layer (Dimensional Model - Star Schema) - Streaming Mode**

Mở terminal mới khác và chạy:

```bash
docker exec -it spark-master bash -c "/opt/spark/bin/spark-submit \
  --packages io.delta:delta-core_2.12:2.4.0,org.apache.hadoop:hadoop-aws:3.3.4 \
  --conf 'spark.sql.extensions=io.delta.sql.DeltaSparkSessionExtension' \
  --conf 'spark.sql.catalog.spark_catalog=org.apache.spark.sql.delta.catalog.DeltaCatalog' \
  /app/gold_layer_dimfact_job.py"
```

**Kết quả:**
- Job sẽ chạy liên tục, tự động xử lý dữ liệu mới từ Silver
- Tạo 5 streaming tables song song:
  - `dim_customer` - Dimension table (khách hàng)
  - `dim_merchant` - Dimension table (cửa hàng)
  - `dim_time` - Dimension table (thời gian)
  - `dim_location` - Dimension table (địa điểm)
  - `fact_transactions` - Fact table (giao dịch với metrics)
- Checkpoint được lưu tại `s3a://lakehouse/checkpoints/silver_to_gold/*`
- Trigger mỗi 30 giây để xử lý micro-batch
- **Không tắt terminal này** - để job chạy liên tục

---

**Luồng xử lý hoàn chỉnh (End-to-End):**

```
PostgreSQL INSERT → Debezium CDC → Kafka 
  ↓ (Bronze Streaming - Auto)
Bronze Layer (Delta Lake)
  ↓ (Silver Streaming - 30s trigger)
Silver Layer + Feature Engineering (15 features)
  ↓ (Gold Streaming - 30s trigger)
Gold Layer (Star Schema: 4 Dims + 1 Fact)
```

**Ưu điểm kiến trúc streaming:**
- ✅ **Near Real-time**: Độ trễ ~30-60 giây từ INSERT đến Gold
- ✅ **Tự động**: Không cần trigger thủ công
- ✅ **Scalable**: Xử lý được millions records/day
- ✅ **Fault-tolerant**: Checkpoint đảm bảo exactly-once processing

---

**Bước 3b (Optional): Tạo SQL Views cho Dashboard**

Truy cập Trino và chạy file `sql/gold_layer_views.sql` để tạo 9 views tối ưu:

```bash
# Access Trino CLI (nếu có)
docker exec -it trino trino --catalog lakehouse --schema gold

# Hoặc sử dụng Metabase/DBeaver để chạy từng view trong file:
# - daily_summary
# - hourly_summary
# - state_summary
# - category_summary
# - amount_summary
# - latest_metrics
# - fraud_patterns
# - merchant_analysis
# - time_period_analysis
```

**Bước 3c: Truy cập Metabase để trực quan hóa dữ liệu**

- Truy cập Metabase tại: http://localhost:3000
- Lần đầu đăng nhập: tạo tài khoản admin
- Kết nối Trino/Presto (host: `trino`, port: `8082`, catalog: `lakehouse`, schema: `gold`)
- Query từ dimensional model:

  ```sql
  -- Dashboard metrics (sử dụng views)
  SELECT * FROM lakehouse.gold.daily_summary;
  SELECT * FROM lakehouse.gold.latest_metrics;

  -- Ad-hoc analysis (sử dụng dim/fact)
  SELECT f.*, c.first_name, m.merchant
  FROM lakehouse.gold.fact_transactions f
  JOIN lakehouse.gold.dim_customer c ON f.customer_key = c.customer_key
  JOIN lakehouse.gold.dim_merchant m ON f.merchant_key = m.merchant_key
  WHERE f.is_fraud = '1'
  ORDER BY f.transaction_amount DESC
  LIMIT 10;
  ```

> **Lợi ích Star Schema:**
>
> - Dashboard queries nhanh (pre-joined dimensions)
> - Chatbot linh hoạt (ad-hoc drill-down)
> - Metabase auto-refresh (1-60 phút) cho monitoring gần real-time

**Bước 4: ML Training**

```bash
docker exec -it spark-master bash -c "/opt/spark/bin/spark-submit \
  --packages io.delta:delta-core_2.12:2.4.0,org.apache.hadoop:hadoop-aws:3.3.4 \
  --conf 'spark.sql.extensions=io.delta.sql.DeltaSparkSessionExtension' \
  --conf 'spark.sql.catalog.spark_catalog=org.apache.spark.sql.delta.catalog.DeltaCatalog' \
  /app/ml_training_job.py"
```

---

### 4. Truy cập Services

| Service             | URL                   | Username / Password                             | Ghi chú                                           |
| ------------------- | --------------------- | ----------------------------------------------- | ------------------------------------------------- |
| Spark Master UI     | http://localhost:8080 | Không cần                                       | Monitoring Spark jobs                             |
| MinIO Console       | http://localhost:9001 | `minio` / `minio123`                            | Quản lý buckets và files (Data Lake)              |
| MLflow UI           | http://localhost:5000 | Không cần                                       | ML model tracking & registry                      |
| Kafka UI            | http://localhost:9002 | Không cần                                       | Xem topics, messages, consumer groups             |
| Trino UI            | http://localhost:8085 | Không cần                                       | Query engine monitoring                           |
| Metabase            | http://localhost:3000 | Tùy chọn (ví dụ:`admin@admin.com` / `admin123`) | BI Dashboard, tự tạo tài khoản admin lần đầu      |
| Fraud Detection API | http://localhost:8000 | Không cần                                       | Real-time prediction endpoint                     |
| Kafka Broker        | localhost:9092        | Không cần                                       | Kafka bootstrap server                            |
| PostgreSQL (Source) | localhost:5432        | `postgres` / `postgres`                         | Database `frauddb`                                |
| Metabase DB         | Internal              | `postgres` / `postgres`                         | Database `metabase` (không cần truy cập thủ công) |
| Hive Metastore DB   | Internal (9083)       | `hive` / `hive`                                 | Postgres cho Hive (không expose ra ngoài)         |

> **Lưu ý quan trọng:**
>
> - **MinIO, PostgreSQL:** Credentials cố định trong `docker-compose.yml` (có thể đổi trước khi khởi động).
> - **Metabase:** Tạo tài khoản admin khi truy cập lần đầu, email/password tùy chọn (ví dụ: `admin@admin.com` / `admin123`).
> - **Spark UI, Kafka UI, Trino UI:** Không yêu cầu đăng nhập.
> - **Airflow, MLflow:** Chưa được khởi động trong docker-compose hiện tại (có thể thêm sau).

### 5. Kiểm tra Pipeline

**Check Bronze layer data:**

```bash
# MinIO console: http://localhost:9001
# Navigate to: lakehouse/bronze/transactions/
```

**Check Kafka messages:**

```bash
docker exec -it kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic postgres.public.transactions \
  --from-beginning --max-messages 5
```

### Xác minh CDC (INSERT/UPDATE/DELETE) và giá trị trường `amt`

**1. Lấy trans_num thực tế để test:**

```sql
SELECT trans_num FROM transactions LIMIT 5;
```

**2. Thực hiện các thao tác trên PostgreSQL:**

```sql
-- UPDATE
UPDATE transactions SET amt = amt + 1 WHERE trans_num = '<trans_num thực tế>';
-- DELETE
DELETE FROM transactions WHERE trans_num = '<trans_num thực tế>';
```

**3. Kiểm tra message CDC trên Kafka:**

```bash
docker exec kafka kafka-console-consumer --bootstrap-server localhost:9092 --topic postgres.public.transactions --from-beginning --max-messages 100000 --timeout-ms 3000 2>$null | Select-String -Pattern "<trans_num thực tế>"
```

Kết quả:

- `"op":"c"` = insert, `"op":"u"` = update, `"op":"d"` = delete.
- Trường `amt` sẽ ở dạng mã hóa Base64 (ví dụ: "amt":"Ark=").

**4. Decode giá trị amt (PowerShell):**

```powershell
[System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String("Ark="))
```

Việc decode này chỉ để xem giá trị thực, không ảnh hưởng pipeline.

**5. Xem Kafka messages qua UI:**

Truy cập Kafka UI tại http://localhost:9002 để xem topics, messages, consumer groups qua giao diện web thân thiện.

**Monitor Spark jobs:**

```bash
docker logs -f spark-master
# Or visit Spark UI: http://localhost:8080
```

### 6. Lakehouse Structure

```
s3a://lakehouse/
├── bronze/transactions/          # Raw CDC data from PostgreSQL
├── silver/transactions/          # 15 engineered features
├── gold/                         # Business aggregations
│   ├── daily_summary/
│   ├── hourly_summary/
│   ├── state_summary/
│   └── category_summary/
├── checkpoints/                  # Spark streaming checkpoints
└── models/                       # ML models & artifacts
```

### 7. Model Performance

| Model               | AUC    | Accuracy | Fraud Detection Rate |
| ------------------- | ------ | -------- | -------------------- |
| Random Forest       | 99.99% | 99.76%   | **83.33%** ⭐        |
| Logistic Regression | 99.93% | 99.53%   | 66.67%               |

### 8. Troubleshooting

**Reset hệ thống:**

```bash
docker-compose down -v
docker-compose up -d --build
```

**Check logs:**

```bash
docker logs data-producer
docker logs spark-master
docker logs kafka
```

**MLflow connection issues:**

```bash
docker-compose restart mlflow
docker logs mlflow
```

---

**Architecture:**

**Data Flow:**

```
CSV → PostgreSQL → Debezium CDC → Kafka → Spark Streaming (Bronze)
                                            ↓ (30s micro-batch)
                                          Silver (15 features)
                                            ↓ (30s micro-batch)
                                          Gold (Star Schema)
```

**Streaming Pipeline (3 tầng liên tục):**

```
Bronze Layer (Raw CDC)
  ├── Input: Kafka CDC events
  ├── Processing: Filter tombstones, parse Debezium format
  ├── Output: Delta Lake (append-only)
  └── Checkpoint: s3a://lakehouse/checkpoints/kafka_to_bronze

Silver Layer (Feature Engineering)
  ├── Input: Bronze Delta Lake (streaming read)
  ├── Processing: Data quality + 15 features
  ├── Output: Delta Lake (partitioned by year/month/day)
  └── Checkpoint: s3a://lakehouse/checkpoints/bronze_to_silver

Gold Layer (Dimensional Model)
  ├── Input: Silver Delta Lake (streaming read)
  ├── Processing: Star Schema (4 Dims + 1 Fact)
  ├── Output: 5 Delta Lake tables
  └── Checkpoint: s3a://lakehouse/checkpoints/silver_to_gold/*
```

**Services (11 containers):**

- postgres, debezium, kafka, zookeeper
- minio, spark-master, spark-worker
- data-producer, mlflow, mlflow-db, metastore-db

**Key Features:**

- ✅ Real-time CDC with Debezium
- ✅ **End-to-end streaming pipeline (Bronze → Silver → Gold)**
- ✅ **Near real-time processing (~30-60s latency)**
- ✅ ACID transactions with Delta Lake
- ✅ Exactly-once processing with checkpoints
- ✅ 15 engineered features (geographic, demographic, temporal, amount)
- ✅ 99%+ accuracy fraud detection
- ✅ Star Schema for analytics (Medallion architecture)

---

## Chi tiết kỹ thuật

Xem file `docs/PROJECT_SPECIFICATION.md` để hiểu rõ:

- Kiến trúc hệ thống chi tiết
- Yêu cầu nghiệp vụ
- Data flow và processing layers
- ML pipeline specifications
