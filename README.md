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
├── deployment/                # Infrastructure setup
│   ├── debezium/              # CDC configuration scripts
│   └── minio/                 # MinIO setup
├── docs/                      # Documentation
│   └── PROJECT_SPECIFICATION.md
├── notebooks/                 # Jupyter notebooks (EDA, experiments)
├── services/                  # Microservices
│   ├── data-producer/         # PostgreSQL data simulator
│   └── fraud-detection-api/   # FastAPI prediction service
├── spark/app/                 # Spark jobs
│   ├── streaming_job.py       # Bronze layer (CDC → Delta Lake)
│   ├── silver_layer_job.py    # Feature engineering (15 features)
│   ├── gold_layer_job.py      # Aggregations
│   └── ml_training_job.py     # Model training pipeline
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

### 2. Khởi động

```bash
# Clone repository
git clone https://github.com/bin-bard/real-time-fraud-detection-lakehouse.git
cd real-time-fraud-detection-lakehouse

# Start all services
docker-compose up -d

# Setup MinIO buckets
docker-compose --profile setup run --rm minio-setup

# Setup Debezium CDC (PowerShell)
.\deployment\debezium\setup_debezium.ps1

# Setup Debezium CDC (Linux/Mac)
chmod +x deployment/debezium/setup_debezium.sh
./deployment/debezium/setup_debezium.sh
```

### 3. Chạy Data Pipeline

**Bước 1: Start data producer**

```bash
docker-compose up -d data-producer
```

**Bước 2: Bronze Layer (CDC ingestion)**

```bash
docker exec -it spark-master bash -c "/opt/spark/bin/spark-submit \
  --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.4.1,io.delta:delta-core_2.12:2.4.0,org.apache.hadoop:hadoop-aws:3.3.4 \
  --conf 'spark.sql.extensions=io.delta.sql.DeltaSparkSessionExtension' \
  --conf 'spark.sql.catalog.spark_catalog=org.apache.spark.sql.delta.catalog.DeltaCatalog' \
  /app/streaming_job.py"
```

**Bước 3: Silver Layer (Feature engineering)**

```bash
# Install ML dependencies
docker exec -it spark-master pip install numpy pandas scikit-learn mlflow boto3 psycopg2-binary

# Run feature engineering
docker exec -it spark-master bash -c "/opt/spark/bin/spark-submit \
  --packages io.delta:delta-core_2.12:2.4.0,org.apache.hadoop:hadoop-aws:3.3.4 \
  --conf 'spark.sql.extensions=io.delta.sql.DeltaSparkSessionExtension' \
  --conf 'spark.sql.catalog.spark_catalog=org.apache.spark.sql.delta.catalog.DeltaCatalog' \
  /app/silver_layer_job.py"
```

**Bước 4: Gold Layer (Aggregations)**

```bash
docker exec -it spark-master bash -c "/opt/spark/bin/spark-submit \
  --packages io.delta:delta-core_2.12:2.4.0,org.apache.hadoop:hadoop-aws:3.3.4 \
  --conf 'spark.sql.extensions=io.delta.sql.DeltaSparkSessionExtension' \
  --conf 'spark.sql.catalog.spark_catalog=org.apache.spark.sql.delta.catalog.DeltaCatalog' \
  /app/gold_layer_job.py"
```

**Bước 5: ML Training**

```bash
docker exec -it spark-master bash -c "/opt/spark/bin/spark-submit \
  --packages io.delta:delta-core_2.12:2.4.0,org.apache.hadoop:hadoop-aws:3.3.4 \
  --conf 'spark.sql.extensions=io.delta.sql.DeltaSparkSessionExtension' \
  --conf 'spark.sql.catalog.spark_catalog=org.apache.spark.sql.delta.catalog.DeltaCatalog' \
  /app/ml_training_job.py"
```

### 4. Truy cập Services

| Service         | URL                   | Credentials         |
| --------------- | --------------------- | ------------------- |
| Spark Master UI | http://localhost:8080 | -                   |
| MinIO Console   | http://localhost:9001 | minio / minio123    |
| Kafka           | localhost:9092        | -                   |
| PostgreSQL      | localhost:5432        | postgres / postgres |

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

**5. Giao diện UI Kafka (tùy chọn):**
Có thể thêm Kafdrop vào docker-compose để xem message qua web UI.

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
docker-compose up -d
docker-compose --profile setup run --rm minio-setup
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

## Architecture

**Data Flow:**

```
CSV → PostgreSQL → Debezium CDC → Kafka → Spark Streaming → Delta Lake
                                            ├── Bronze (raw)
                                            ├── Silver (15 features)
                                            └── Gold (aggregations)
```

**Services (11 containers):**

- postgres, debezium, kafka, zookeeper
- minio, spark-master, spark-worker
- data-producer, mlflow, mlflow-db, metastore-db

**Key Features:**

- ✅ Real-time CDC with Debezium
- ✅ ACID transactions with Delta Lake
- ✅ 15 engineered features (geographic, demographic, temporal, amount)
- ✅ 99%+ accuracy fraud detection
- ✅ Medallion architecture (Bronze/Silver/Gold)

---

## Chi tiết kỹ thuật

Xem file `docs/PROJECT_SPECIFICATION.md` để hiểu rõ:

- Kiến trúc hệ thống chi tiết
- Yêu cầu nghiệp vụ
- Data flow và processing layers
- ML pipeline specifications
