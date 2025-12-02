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
│   │   ├── streaming_job.py   # Bronze: Kafka CDC → Delta Lake (continuous)
│   │   ├── silver_job.py      # Silver: Feature engineering (batch every 5 min)
│   │   ├── gold_job.py        # Gold: Star Schema (batch every 5 min)
│   │   ├── ml_training_job.py # Model training pipeline
│   │   ├── run_silver.sh      # Shell wrapper for silver batch
│   │   └── run_gold.sh        # Shell wrapper for gold batch
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

### Feature Engineering (40 features)

**Geographic** (2): `distance_km` (Haversine), `is_distant_transaction`  
**Demographic** (2): `age`, `gender_encoded`  
**Time** (6): `hour`, `day_of_week`, `is_weekend`, `is_late_night`, `hour_sin`, `hour_cos`  
**Amount** (4): `log_amount`, `amount_bin`, `is_zero_amount`, `is_high_amount`  
**Original** (26): All columns from Bronze layer preserved

## Kiến trúc hệ thống

### Medallion Architecture (Hybrid: Streaming + Batch)

Hệ thống sử dụng **kiến trúc lai** để tối ưu CPU và latency:

```
PostgreSQL (Source)
    ↓ Debezium CDC
Kafka (postgres.public.transactions)
    ↓ Bronze Streaming (Continuous, ~195% CPU)
Bronze Delta Lake (s3a://lakehouse/bronze/)
    ↓ Silver Batch (Every 5 minutes, 0% CPU during sleep)
Silver Delta Lake (s3a://lakehouse/silver/)
    ↓ Gold Batch (Every 5 minutes, 0% CPU during sleep)
Gold Delta Lake (s3a://lakehouse/gold/) - 5 tables
    ↓ Trino Delta Catalog (Direct access, no Hive Metastore)
Query Layer (Trino + Metabase)
```

**Lợi ích:**
- ✅ **Bronze Layer**: Real-time CDC capture từ Kafka (streaming liên tục)
- ✅ **Silver Layer**: Feature engineering mỗi 5 phút (batch) - giảm 60% CPU
- ✅ **Gold Layer**: Star schema mỗi 5 phút (batch) - data sẵn sàng cho analytics
- ✅ **Latency**: 5-10 phút từ source đến Gold (chấp nhận được cho fraud detection analytics)
- ✅ **Resource**: Bronze ~195% CPU, Silver/Gold 0% CPU khi sleep

### Delta Lake Integration

**Không sử dụng Hive Metastore** - Delta Lake tự quản lý metadata qua `_delta_log/`:
- ✅ ACID transactions
- ✅ Time travel (Delta Lake history)
- ✅ Schema evolution với `overwriteSchema=true`
- ✅ Trino query trực tiếp qua Delta catalog

## Hướng dẫn chạy

### 1. Yêu cầu hệ thống

- Docker & Docker Compose
- Python 3.9+
- 8GB RAM, 20GB disk space

---

### 2. Khởi động hệ thống

```bash
# Clone repository
git clone https://github.com/bin-bard/real-time-fraud-detection-lakehouse.git
cd real-time-fraud-detection-lakehouse

# Khởi động toàn bộ hệ thống
docker-compose up -d
```

> **Lưu ý:** Tất cả services tự động start, bao gồm Bronze streaming và Silver/Gold batch jobs.

---

### 3. Kiểm tra Data Pipeline

Pipeline tự động chạy với **3 Spark jobs**:

#### Kiểm tra logs

```bash
# Xem tất cả 3 jobs
docker-compose logs -f bronze-streaming silver-job gold-job

# Hoặc từng job riêng lẻ
docker logs -f bronze-streaming    # Bronze: CDC → Delta Lake
docker logs -f silver-job          # Silver: Feature engineering (every 5 min)
docker logs -f gold-job            # Gold: Star schema (every 5 min)
```

#### Verify thành công

**Bronze streaming** (continuous):
```
Writing batch 100 to Bronze layer...
Batch 100 written to Bronze successfully.
```

**Silver batch** (every 5 minutes):
```
🥈 Starting Bronze to Silver layer BATCH processing...
Found 86427 new records to process
✅ Successfully processed 86427 records to Silver layer!
✅ Silver batch completed. Sleeping 5 minutes...
```

**Gold batch** (every 5 minutes):
```
✨ Gold layer batch processing completed!
📊 Processed 86527 records from Silver layer
📊 Updated tables:
   - dim_customer -> s3a://lakehouse/gold/dim_customer
   - dim_merchant -> s3a://lakehouse/gold/dim_merchant
   - dim_time -> s3a://lakehouse/gold/dim_time
   - dim_location -> s3a://lakehouse/gold/dim_location
   - fact_transactions -> s3a://lakehouse/gold/fact_transactions
```

#### Kiểm tra CPU usage

```bash
docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}" | grep -E "bronze|silver|gold"
```

**Output mong đợi:**
```
bronze-streaming   195.96%   935.5MiB / 7.76GiB
silver-job         0.00%     219.5MiB / 7.76GiB
gold-job           0.00%     2.555MiB / 7.76GiB
```

✅ **Bronze**: ~195% CPU (streaming liên tục)  
✅ **Silver**: 0% CPU (đang sleep 5 phút)  
✅ **Gold**: 0% CPU (đang sleep 5 phút)

---

### 4. Cấu trúc Spark Jobs

#### Bronze Layer (`streaming_job.py`)
- **Mode**: Structured Streaming (continuous)
- **Input**: Kafka topic `postgres.public.transactions`
- **Processing**: Parse Debezium CDC format (`$.after.*`)
- **Output**: Delta Lake `s3a://lakehouse/bronze/transactions`
- **Partitioning**: By `year`, `month`, `day`

#### Silver Layer (`silver_job.py`)
- **Mode**: Batch (every 5 minutes)
- **Input**: Bronze Delta Lake
- **Processing**: 
  - Data quality checks
  - Type casting (String → Double/Long/Date)
  - Feature engineering (40 features)
  - Incremental processing (only new data)
- **Output**: Delta Lake `s3a://lakehouse/silver/transactions`
- **Config**: Ancient date support (`datetimeRebaseModeInWrite=LEGACY`)

#### Gold Layer (`gold_job.py`)
- **Mode**: Batch (every 5 minutes)
- **Input**: Silver Delta Lake
- **Processing**: 
  - Star schema transformation
  - Hash-based surrogate keys
  - Incremental processing
- **Output**: 5 Delta tables
  - `dim_customer`: Customer dimension (cc_num, first, last, gender, dob, etc.)
  - `dim_merchant`: Merchant dimension (merchant, category, merch_lat, merch_long)
  - `dim_time`: Time dimension (date, hour, day_of_week, is_weekend)
  - `dim_location`: Location dimension (city, state, zip, lat, long)
  - `fact_transactions`: Fact table (foreign keys + measures)
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

### 5. Query Data với Trino

Trino có thể query trực tiếp Delta Lake tables **không cần Hive Metastore**:

```sql
-- Truy cập Trino CLI
docker exec -it trino trino

-- List catalogs
SHOW CATALOGS;

-- Query Bronze layer
SELECT COUNT(*) FROM delta.default."s3a://lakehouse/bronze/transactions";

-- Query Silver layer (với features)
SELECT trans_num, amt, distance_km, age, is_fraud 
FROM delta.default."s3a://lakehouse/silver/transactions"
LIMIT 10;

-- Query Gold layer - Star Schema
SELECT 
  f.transaction_amount,
  c.first_name || ' ' || c.last_name AS customer_name,
  m.merchant_name,
  t.hour,
  l.state
FROM delta.default."s3a://lakehouse/gold/fact_transactions" f
JOIN delta.default."s3a://lakehouse/gold/dim_customer" c ON f.customer_key = c.customer_key
JOIN delta.default."s3a://lakehouse/gold/dim_merchant" m ON f.merchant_key = m.merchant_key
JOIN delta.default."s3a://lakehouse/gold/dim_time" t ON f.time_key = t.time_key
JOIN delta.default."s3a://lakehouse/gold/dim_location" l ON f.location_key = l.location_key
WHERE f.is_fraud = 1
LIMIT 20;
```

---

### 6. Truy cập Services

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

---

### 7. Troubleshooting & Maintenance

#### Reset toàn bộ hệ thống

```bash
docker-compose down -v
docker-compose up -d --build
```

#### Check logs khi có lỗi

```bash
# Check Bronze streaming
docker logs bronze-streaming --tail 50

# Check Silver batch
docker logs silver-job --tail 50

# Check Gold batch  
docker logs gold-job --tail 50

# Check Spark Master
docker logs spark-master
```

#### Common issues

**High CPU usage**:
- Bronze streaming: ~195% CPU (bình thường)
- Silver/Gold batch: 0% CPU khi sleep, spike khi chạy (bình thường)
- Nếu cả 3 jobs đều >200% CPU: Xem xét giảm batch size hoặc tăng sleep interval

**Job fails to start**:
- Check Spark Master UI: http://localhost:8080
- Verify MinIO accessible: http://localhost:9001
- Check Kafka messages: `docker logs kafka`

---

### 8. Lakehouse Structure

```
s3a://lakehouse/
├── bronze/transactions/          # Raw CDC data (Debezium format parsed)
│   └── _delta_log/              # Delta Lake transaction logs
├── silver/transactions/          # 40 engineered features
│   └── _delta_log/
├── gold/                         # Star Schema (5 tables)
│   ├── dim_customer/
│   ├── dim_merchant/
│   ├── dim_time/
│   ├── dim_location/
│   └── fact_transactions/
├── checkpoints/                  # Spark streaming checkpoints
│   ├── kafka_to_bronze/         # Bronze streaming state
│   ├── bronze_to_silver_batch/  # Silver batch watermark
│   └── silver_to_gold_batch/    # Gold batch watermark
└── models/                       # ML models & artifacts (future)
```

---

### 9. Kiến trúc Data Flow

**Luồng xử lý hoàn chỉnh:**

```
PostgreSQL INSERT
    ↓ Debezium CDC (Change Data Capture)
Kafka Topic: postgres.public.transactions
    ↓ Bronze Streaming (Continuous, ~195% CPU)
Bronze Delta Lake (s3a://lakehouse/bronze/)
    ↓ Silver Batch (Every 5 minutes, spike to ~100% CPU then sleep)
Silver Delta Lake (40 features, s3a://lakehouse/silver/)
    ↓ Gold Batch (Every 5 minutes, spike to ~100% CPU then sleep)
Gold Delta Lake (5 tables, s3a://lakehouse/gold/)
    ↓ Trino Delta Catalog (Direct query, no Hive Metastore)
Metabase Dashboard / Analytics
```

**Latency:**
- Bronze: Real-time (~1-2 seconds from PostgreSQL INSERT)
- Silver: 5-10 minutes (batch interval + processing time)
- Gold: 10-15 minutes (waits for Silver + processing time)

**Resource Usage:**
- Bronze: 195% CPU (continuous streaming)
- Silver: 0% CPU (95% of time), spike when processing
- Gold: 0% CPU (95% of time), spike when processing
- **Total**: ~195-400% CPU (depending on batch cycle)

---

### 10. Services Container Map

| Service             | URL                   | Credentials             | Purpose                                  |
| ------------------- | --------------------- | ----------------------- | ---------------------------------------- |
| Spark Master UI     | http://localhost:8080 | None                    | Monitor Spark jobs & resource allocation |
| MinIO Console       | http://localhost:9001 | minio / minio123        | S3-compatible Data Lake storage          |
| MLflow UI           | http://localhost:5000 | None                    | ML model tracking & registry             |
| Kafka UI            | http://localhost:9002 | None                    | Kafka topics & messages monitoring       |
| Trino UI            | http://localhost:8085 | None                    | Distributed SQL query engine             |
| Metabase            | http://localhost:3000 | admin@admin.com / admin | BI Dashboard & visualization             |
| Fraud Detection API | http://localhost:8000 | None                    | Real-time prediction endpoint (future)   |
| Kafka Broker        | localhost:9092        | None                    | Message streaming platform               |
| PostgreSQL          | localhost:5432        | postgres / postgres     | Source database (frauddb)                |

---

### 11. Key Features & Achievements

✅ **Hybrid Architecture**: Streaming (Bronze) + Batch (Silver/Gold) for optimal CPU usage  
✅ **Real-time CDC**: Debezium captures INSERT/UPDATE/DELETE from PostgreSQL  
✅ **ACID Transactions**: Delta Lake ensures data consistency  
✅ **Incremental Processing**: Only process new data (watermark-based)  
✅ **Schema Evolution**: Support for ancient dates with LEGACY mode  
✅ **40 Features**: Geographic, demographic, time-based, amount-based  
✅ **Star Schema**: 4 dimensions + 1 fact table for analytics  
✅ **Direct Trino Query**: No Hive Metastore dependency  
✅ **60% CPU Reduction**: From 300%+ to ~195% by moving to batch processing  

---

## Chi tiết kỹ thuật

Xem file `docs/PROJECT_SPECIFICATION.md` để hiểu rõ:

- Kiến trúc hệ thống chi tiết
- Yêu cầu nghiệp vụ
- Data flow và processing layers
- ML pipeline specifications
