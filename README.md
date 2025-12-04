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

| Component         | Technology               | Mô tả                                       |
| ----------------- | ------------------------ | ------------------------------------------- |
| **Source DB**     | PostgreSQL 14            | OLTP database với CDC enabled               |
| **CDC**           | Debezium 2.5             | Change Data Capture connector               |
| **Streaming**     | Apache Kafka             | Message broker                              |
| **Processing**    | Apache Spark 3.4.1       | Stream & batch processing                   |
| **Storage**       | Delta Lake 2.4.0 + MinIO | ACID transactions, time travel              |
| **Metastore**     | Hive Metastore 3.1.3     | Metadata cache for Delta catalog (optional) |
| **Query Engine**  | Trino (Delta connector)  | Distributed SQL query engine                |
| **Visualization** | Metabase                 | BI dashboards & analytics                   |
| **ML**            | Scikit-learn, MLflow     | Model training & registry                   |
| **API**           | FastAPI                  | Real-time prediction service                |
| **Orchestration** | Apache Airflow           | Workflow scheduling                         |

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
    ↓
    ├─→ Hive Metastore (Metadata cache: SHOW TABLES nhanh)
    └─→ Trino Delta Catalog (Query data: đọc từ _delta_log/ + S3)
Query Layer (Metabase/DBeaver via Delta catalog)
```

**Lợi ích:**

- ✅ **Bronze Layer**: Real-time CDC capture từ Kafka (streaming liên tục)
- ✅ **Silver Layer**: Feature engineering mỗi 5 phút (batch) - giảm 60% CPU
- ✅ **Gold Layer**: Star schema mỗi 5 phút (batch) - data sẵn sàng cho analytics
- ✅ **Latency**: 5-10 phút từ source đến Gold (chấp nhận được cho fraud detection analytics)
- ✅ **Resource**: Bronze ~195% CPU, Silver/Gold 0% CPU khi sleep

### Delta Lake Integration

Delta Lake tự quản lý metadata qua `_delta_log/`, **Hive Metastore chỉ là metadata cache** (optional):

- ✅ **ACID transactions**: Delta Lake đảm bảo consistency
- ✅ **Time travel**: Lịch sử thay đổi trong `_delta_log/`
- ✅ **Schema evolution**: Tự động với `overwriteSchema=true`
- ✅ **Query engine**: Trino Delta connector đọc trực tiếp từ S3 + `_delta_log/`
- 🔄 **Hive Metastore**: Cache metadata để `SHOW TABLES` nhanh hơn (~100ms vs ~1-2s)

**Lưu ý quan trọng:**

- 📊 **Query data**: Dùng Delta catalog (`delta.bronze.*`, `delta.silver.*`, `delta.gold.*`)
- 📋 **List tables**: Có thể dùng Hive catalog (`hive.*`) nhưng KHÔNG query được
- ⚡ **Performance**: Hive cache giúp discovery operations nhanh hơn 10-20 lần

## Hướng dẫn chạy

### 1. Yêu cầu hệ thống

**Phần cứng tối thiểu:**

- **CPU**: 6 cores (khuyến nghị 8+ cores)
- **RAM**: 10GB (khuyến nghị 16GB)
- **Disk**: 30GB trống

**Phần mềm:**

- Docker Desktop 4.0+ (Windows/Mac) hoặc Docker Engine 20.10+ (Linux)
- Docker Compose 2.0+
- PowerShell 5.1+ (Windows) hoặc Bash (Linux/Mac)

**Cấu hình Docker (Windows WSL2):**

Tạo file `C:\Users\<YourUsername>\.wslconfig`:

```ini
[wsl2]
memory=10GB
processors=6
swap=4GB
```

Sau đó restart WSL2:

```powershell
wsl --shutdown
```

---

### 2. Khởi động hệ thống lần đầu

```bash
# Clone repository
git clone https://github.com/bin-bard/real-time-fraud-detection-lakehouse.git
cd real-time-fraud-detection-lakehouse

# Khởi động toàn bộ hệ thống
docker compose up -d --build
```

**⏳ Thời gian khởi động:** ~5-10 phút (tải images + khởi tạo services)

> **Lưu ý quan trọng:**
>
> - Tất cả services tự động start
> - Bronze streaming chạy liên tục (real-time CDC)
> - Silver/Gold jobs chạy batch mỗi 5 phút qua Airflow DAG
> - Data producer tự động insert dữ liệu vào PostgreSQL

---

### 3. Kiểm tra hệ thống đã khởi động

#### Verify tất cả containers đang chạy

```bash
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

**Output mong đợi:** 15+ containers với status `Up`

#### Kiểm tra logs Pipeline

````bash
# Bronze streaming (real-time CDC)
docker logs -f bronze-streaming

# Airflow scheduler (quản lý batch jobs)
#### Verify Pipeline hoạt động

**1. Bronze Layer (Real-time CDC):**

```bash
docker logs bronze-streaming --tail 20
````

Log thành công:

```
25/12/04 14:10:46 INFO ProcessingTimeMicroBatchStream: Batch 5 processing started
25/12/04 14:10:47 INFO WriteToDataSourceV2: Writing 142 records to Bronze layer...
25/12/04 14:10:48 INFO WriteToDataSourceV2: ✅ Batch 5 written successfully
```

**2. Airflow DAG (Batch ETL):**

- Truy cập Airflow UI: http://localhost:8081 (`admin`/`admin`)
- Check DAG `lakehouse_pipeline_taskflow` (chạy mỗi 5 phút)
- Xem task logs để verify Silver/Gold processing

**3. Data trong MinIO:**

- Truy cập MinIO Console: http://localhost:9001 (`minio`/`minio123`)
- Navigate: `lakehouse/bronze/transactions/` → verify có Parquet files
- Navigate: `lakehouse/silver/transactions/` → verify có data (sau ~5 phút)
- Navigate: `lakehouse/gold/` → verify có 5 folders (dim*\*, fact*\*)

**4. Trino Query (verify end-to-end):**

```bash
docker exec -it trino trino --server localhost:8081
```

````sql
-- ⚠️ IMPORTANT: Query via DELTA catalog (not HIVE)
-- Hive catalog can list tables but cannot query Delta format

-- Kiểm tra số lượng records
SELECT COUNT(*) FROM delta.bronze.transactions;
SELECT COUNT(*) FROM delta.silver.transactions;
SELECT COUNT(*) FROM delta.gold.fact_transactions;

-- Sample data
SELECT * FROM delta.gold.fact_transactions LIMIT 5;

-- Exit
quit;
```/ 7.76GiB
gold-job           0.00%     2.555MiB / 7.76GiB
````

✅ **Bronze**: ~195% CPU (streaming liên tục)  
✅ **Silver**: 0% CPU (đang sleep 5 phút)  
✅ **Gold**: 0% CPU (đang sleep 5 phút)

---

### 4. Cấu trúc Spark Jobs & Data Flow

#### Kiến trúc xử lý dữ liệu

```
PostgreSQL (Source DB)
    ↓ Debezium CDC (Change Data Capture)
Kafka Topic: postgres.public.transactions
    ↓ Bronze Streaming Job (Continuous, ~195% CPU)
Bronze Delta Lake (s3a://lakehouse/bronze/)
    ↓ Silver Batch Job (Every 5 min via Airflow)
Silver Delta Lake (40 features, s3a://lakehouse/silver/)
    ↓ Gold Batch Job (Every 5 min via Airflow)
Gold Delta Lake (5 tables, s3a://lakehouse/gold/)
    ↓ Hive Metastore Registration (Auto via Airflow)
    ↓ Trino Query Engine (hive catalog)
Metabase Dashboard / Analytics
```

#### Bronze Layer (`streaming_job.py`)

**Mode:** Structured Streaming (continuous)  
**Input:** Kafka topic `postgres.public.transactions`  
**Processing:**

- Parse Debezium CDC format (`$.after.*`)
- Extract 22 fields từ JSON payload
- Add metadata: `ingestion_time`, partition keys (`year`, `month`, `day`)

**Output:** Delta Lake `s3a://lakehouse/bronze/transactions`  
**Trigger:** Continuous (processAvailableNow)  
**Checkpoint:** `s3a://lakehouse/checkpoints/kafka_to_bronze`

**Container:** `bronze-streaming` (auto-start)

```bash
# Xem logs
docker logs -f bronze-streaming
```

#### Silver Layer (`silver_job.py`)

**Mode:** Batch (triggered by Airflow every 5 minutes)  
**Input:** Bronze Delta Lake  
**Processing:**

- **Incremental:** Chỉ xử lý records mới (watermark-based)
- Type casting (String → Double/Long/Date)
- Data quality checks (fillna, outliers)
- **Feature Engineering:** 40 features
  - Geographic: `distance_km`, `is_distant_transaction`
  - Demographic: `age`, `gender_encoded`
  - Time: `hour`, `day_of_week`, `is_weekend`, `is_late_night`, `hour_sin`, `hour_cos`
  - Amount: `log_amount`, `amount_bin`, `is_zero_amount`, `is_high_amount`

**Output:** Delta Lake `s3a://lakehouse/silver/transactions`  
**Partitioning:** By `year`, `month`, `day`  
**Schema Evolution:** `overwriteSchema=true` (support ancient dates với LEGACY mode)

**Trigger:** Airflow DAG `lakehouse_pipeline_taskflow` task `run_silver_transformation`

```bash
# Xem logs trong Airflow UI
http://localhost:8081 → lakehouse_pipeline_taskflow → run_silver_transformation → Logs
```

#### Gold Layer (`gold_job.py`)

**Mode:** Batch (triggered by Airflow every 5 minutes)  
**Input:** Silver Delta Lake  
**Processing:**

- **Star Schema transformation**
- Hash-based surrogate keys (MD5)
- **Incremental:** Chỉ xử lý records mới từ Silver

**Output:** 5 Delta tables

1. **`dim_customer`** - Customer dimension
   - `customer_key` (PK), `cc_num`, `first`, `last`, `gender`, `dob`, `job`
2. **`dim_merchant`** - Merchant dimension
   - `merchant_key` (PK), `merchant`, `category`, `merch_lat`, `merch_long`
3. **`dim_time`** - Time dimension
   - `time_key` (PK), `trans_date`, `hour`, `day_of_week`, `is_weekend`, `is_late_night`
4. **`dim_location`** - Location dimension
   - `location_key` (PK), `city`, `state`, `zip`, `lat`, `long`, `city_pop`
5. **`fact_transactions`** - Fact table
   - Foreign keys: `customer_key`, `merchant_key`, `time_key`, `location_key`
   - Measures: `amt`, `distance_km`, `age`, `is_fraud`
   - Degenerate dimensions: `trans_num`, `trans_timestamp`

**Trigger:** Airflow DAG `lakehouse_pipeline_taskflow` task `run_gold_transformation`

```bash
# Xem logs trong Airflow UI
http://localhost:8081 → lakehouse_pipeline_taskflow → run_gold_transformation → Logs
```

#### Hive Metastore Registration (Optional Metadata Cache)

**Vai trò**: Hive Metastore là **metadata cache layer** giúp `SHOW TABLES` nhanh hơn.

**Mode:** Auto-registration via Airflow  
**Trigger:** Sau khi Gold job hoàn thành  
**Tables registered:** 7 tables (Bronze, Silver, Gold)

**⚠️ QUAN TRỌNG - Hiểu đúng vai trò:**

- ✅ **Hive catalog** (`hive.*`): List metadata (SHOW TABLES) - nhanh
- ❌ **Hive catalog**: KHÔNG query được Delta tables (lỗi "Cannot query Delta Lake table")
- ✅ **Delta catalog** (`delta.*`): Query data thực tế - BẮT BUỘC dùng cho SELECT

**Có thể bỏ Hive Metastore không?**

- CÓ - Delta connector tự discover tables từ S3
- NHƯNG: `SHOW TABLES` sẽ chậm hơn (scan MinIO mỗi lần)
- KHUYẾN NGHỊ: Giữ lại để tối ưu performance (đã config sẵn)

```bash
docker exec -it trino trino --server localhost:8081
```

```sql
-- List catalogs và schemas
SHOW CATALOGS;  -- Expect: delta, hive, system
SHOW SCHEMAS FROM delta;  -- Expect: bronze, silver, gold

-- List tables (Cả 2 catalog đều OK)
SHOW TABLES FROM delta.gold;  -- ✅ Khuyến nghị (consistent)
SHOW TABLES FROM hive.gold;   -- ✅ OK (từ metadata cache)
-- Output: dim_customer, dim_merchant, dim_time, dim_location, fact_transactions

-- ⚠️ QUAN TRỌNG: Query data CHỈ dùng Delta catalog!
-- Lý do: Hive connector KHÔNG đọc được Delta format

-- ✅ ĐÚNG - Query via Delta catalog
SELECT COUNT(*) FROM delta.bronze.transactions;
SELECT COUNT(*) FROM delta.silver.transactions;
SELECT COUNT(*) FROM delta.gold.fact_transactions;

-- ❌ SAI - Query via Hive catalog (sẽ lỗi!)
-- SELECT COUNT(*) FROM hive.bronze.transactions;  -- Error: Cannot query Delta Lake table

quit;
```

---

### 6. Truy cập Services

| Service             | URL                   | Username / Password                             | Ghi chú                                           |
| ------------------- | --------------------- | ----------------------------------------------- | ------------------------------------------------- |
| **Airflow**         | http://localhost:8081 | `admin` / `admin`                               | Workflow orchestration & DAG management           |
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
> - **Airflow:** Tài khoản mặc định `admin/admin` (đã được tự động tạo khi khởi động).
> - **Spark UI, Kafka UI, Trino UI:** Không yêu cầu đăng nhập.

#### Kết nối Trino qua DBeaver/SQL Client

Để truy vấn dữ liệu Lakehouse qua SQL client (DBeaver, DataGrip, v.v.):

**Thông tin kết nối:**

- **Driver**: Trino (hoặc Presto)
- **Host**: `localhost`
- **Port**: `8085`
- **Database/Catalog**: `delta` ⚠️ (KHÔNG phải `hive`)
- **Schema**: `gold`, `silver`, hoặc `bronze`
- **Username**: `trino` (hoặc bất kỳ)
- **Password**: để trống
- **JDBC URL**: `jdbc:trino://localhost:8085/delta`

**⚠️ QUAN TRỌNG:** Dùng catalog `delta` để query, không phải `hive`!

**Ví dụ truy vấn:**

```sql
-- Xem tất cả schemas
SHOW SCHEMAS FROM delta;

-- Xem tables trong Gold layer
SHOW TABLES FROM delta.gold;

-- Query fact table
SELECT * FROM delta.gold.fact_transactions LIMIT 10;

-- Join với dimension tables
SELECT
    f.trans_num,
    c.first_name,
    c.last_name,
    m.merchant_name,
    f.amt,
    f.is_fraud
FROM delta.gold.fact_transactions f
JOIN delta.gold.dim_customer c ON f.customer_key = c.customer_key
JOIN delta.gold.dim_merchant m ON f.merchant_key = m.merchant_key
WHERE f.is_fraud = 1
LIMIT 20;
```

---

### 7. Airflow Workflow Orchestration

Hệ thống sử dụng **Apache Airflow 2.8.0** để quản lý các workflow batch processing:

#### Truy cập Airflow UI

```bash
# URL: http://localhost:8081
# Username: admin
# Password: admin
```

#### DAGs có sẵn

**1. `lakehouse_pipeline_taskflow`** - Lakehouse ETL Pipeline (TaskFlow API)

- **Schedule**: Mỗi 5 phút (`*/5 * * * *`)
- **Tasks**:
  1. `check_bronze_data` - Kiểm tra Bronze streaming đang chạy
  2. `run_silver_transformation` - Chạy Silver job (Bronze → Features)
  3. `run_gold_transformation` - Chạy Gold job (Silver → Star Schema)

### 5. Airflow Workflow Orchestration

Hệ thống sử dụng **Apache Airflow 2.8.0** để quản lý batch ETL và ML training:

#### Truy cập Airflow UI

**URL:** http://localhost:8081  
**Credentials:** `admin` / `admin`

#### DAGs có sẵn

**1. `lakehouse_pipeline_taskflow`** - Batch ETL Pipeline

- **Schedule**: Mỗi 5 phút (`*/5 * * * *`)
- **Mục đích**: Transform Bronze → Silver → Gold
- **Tasks**:
  1. ✅ `check_bronze_data` - Verify Bronze có data mới
  2. 🔄 `run_silver_transformation` - Feature engineering (40 features)
  3. ⭐ `run_gold_transformation` - Star schema (5 tables)
  4. 📋 `register_tables_to_hive` - Register vào Hive Metastore
  5. ✔️ `verify_trino_access` - Test Trino query
  6. 📊 `send_pipeline_summary` - Log summary

**Xem logs:**

```bash
# Trong Airflow UI
DAGs → lakehouse_pipeline_taskflow → Graph → Click task → Logs

# Hoặc check summary trong logs
docker logs airflow-scheduler | grep "LAKEHOUSE PIPELINE"
```

**Output mẫu:**

```
[2025-12-04, 21:16:50] INFO - ============================================================
[2025-12-04, 21:16:50] INFO - Bronze Check: ready
[2025-12-04, 21:16:50] INFO - Silver Status: success
[2025-12-04, 21:16:50] INFO -   - Records Processed: 8,547
[2025-12-04, 21:16:50] INFO - Gold Status: success
[2025-12-04, 21:16:50] INFO -   - Tables Created: 5
[2025-12-04, 21:16:50] INFO - Hive Registration: success
[2025-12-04, 21:16:50] INFO -   - Tables Registered: 7
[2025-12-04, 21:16:50] INFO - Trino Verification: verified
[2025-12-04, 21:16:50] INFO - ============================================================
```

---

**2. `model_retraining_taskflow`** - ML Model Training

- **Schedule**: Hàng ngày lúc 02:00 AM (`0 2 * * *`)
- **Mục đích**: Train RandomForest + LogisticRegression models
- **Tasks**:
  1. 📊 `check_data_availability` - Verify Silver layer có data
  2. 🧠 `train_ml_models` - Train 2 models với MLflow tracking
  3. ✅ `verify_models_registered` - Check MLflow registry
  4. 📬 `send_notification` - Training summary

**⚠️ Quan trọng - Resource Management:**

ML training tiêu tốn nhiều CPU/RAM. **Trước khi chạy**, giải phóng tài nguyên:

```powershell
# Tắt services không cần thiết (giải phóng ~2GB RAM + 1-2 CPU cores)
.\scripts\prepare-ml-training.ps1

# Sau đó trigger DAG qua Airflow UI hoặc:
# Airflow UI → model_retraining_taskflow → Trigger DAG (▶️)

# Sau khi training xong, khôi phục services
.\scripts\restore-services.ps1
```

**Services bị tắt khi training:**

- ❌ Trino (query engine - không cần cho training)
- ❌ Metabase (dashboard - không cần cho training)
- ❌ Hive Metastore (catalog - training dùng Delta trực tiếp)
- ❌ Debezium (CDC connector - tạm dừng data ingestion)
- ❌ Data Producer (data generator - tạm dừng)

**Services vẫn chạy:**

- ✅ Spark (master + worker) - Chạy training job
- ✅ MLflow - Track experiments và lưu models
- ✅ MinIO - Storage cho Delta Lake + artifacts
- ✅ PostgreSQL - Airflow DB + MLflow backend
- ✅ Airflow - Orchestration

**Spark config tối ưu cho training:**

```python
'--conf', 'spark.cores.max=2',           # Giảm từ 4→2 cores
'--conf', 'spark.executor.cores=1',      # 1 core/executor
'--conf', 'spark.executor.memory=1g',    # Giảm từ 2g→1g
'--conf', 'spark.driver.memory=1g',      # Giảm từ 2g→1g
```

**Xem training logs:**

```bash
# Trong Airflow UI
DAGs → model_retraining_taskflow → Graph → train_ml_models → Logs

# Hoặc check Spark job output
docker logs spark-master | grep "FraudDetectionMLTraining"
```

**Verify models trong MLflow:**

- Truy cập MLflow UI: http://localhost:5000
- Check experiment `fraud_detection_production`
- Verify có 2 registered models: `fraud_detection_random_forest`, `fraud_detection_logistic_regression`

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

### 7. Query Data với Trino + Metabase

#### Kiểm tra Tables đã được Register

Hệ thống tự động register Delta Lake tables vào Hive Metastore mỗi giờ:

```bash
# Kiểm tra registration logs
docker logs hive-registration --tail 30

# Verify tables trong Trino
docker exec trino trino --server localhost:8081 --execute "SHOW TABLES FROM delta.gold"
```

**Output mong đợi:**

```
"dim_customer"
"dim_location"
"dim_merchant"
"dim_time"
"fact_transactions"
```

#### Kết nối Metabase

1. **Truy cập Metabase:** http://localhost:3000
2. **First-time setup:** Tạo tài khoản admin
3. **Add Database:**
   - Database type: **Trino**
   - Display name: `Fraud Detection Lakehouse`
   - Host: `trino`
   - Port: `8081`
   - Catalog: `delta`
   - Database: `gold`
   - Username/Password: (để trống)
4. **Save** → Metabase sẽ sync metadata

#### Sample Queries

````sql
-- Fraud rate by merchant category
SELECT
  dm.category,
  COUNT(*) as total_transactions,
  SUM(CASE WHEN ft.is_fraud = true THEN 1 ELSE 0 END) as fraud_count,
### 6. Troubleshooting & Maintenance

#### Reset toàn bộ hệ thống

**Cảnh báo:** Xóa toàn bộ data và volumes!

```bash
docker compose down -v
docker compose up -d --build
````

#### Xóa chỉ data lakehouse (giữ lại containers)

```bash
# Stop data ingestion
docker compose stop data-producer bronze-streaming

# Xóa Delta Lake data (PowerShell)
docker exec minio mc rm -r --force lakehouse/bronze/ lakehouse/silver/ lakehouse/gold/ lakehouse/checkpoints/

# Restart pipeline
docker compose up -d bronze-streaming data-producer
```

#### Check logs khi có lỗi

```bash
# Airflow scheduler (quản lý DAGs)
docker logs airflow-scheduler --tail 100

# Bronze streaming (CDC ingestion)
docker logs bronze-streaming --tail 50

# Spark Master (job allocation)
docker logs spark-master --tail 50

# MLflow (model tracking)
docker logs mlflow --tail 50
```

#### Common Issues

**1. Airflow task timeout (SIGTERM)**

**Nguyên nhân:** Spark job chiếm quá nhiều CPU → Airflow DB connection timeout

**Giải pháp:**

```powershell
# Giải phóng tài nguyên trước khi chạy ML training
.\scripts\prepare-ml-training.ps1
```

**2. High CPU usage (>500%)**

**Kiểm tra:**

```bash
docker stats --no-stream
```

**Bình thường:**

- `bronze-streaming`: ~195% CPU (continuous)
- `spark-master`: ~50-100% CPU khi có job
- `airflow-*`: ~10-30% CPU

**Bất thường:** Nếu tổng CPU >600%, restart services:

```bash
docker compose restart bronze-streaming spark-master spark-worker
```

**3. No data in Silver/Gold**

**Debug:**

```bash
# 1. Check Bronze có data không
docker exec -it trino trino --execute "SELECT COUNT(*) FROM hive.bronze.transactions"

# 2. Check Airflow DAG lakehouse_pipeline_taskflow có chạy không
# → Airflow UI: http://localhost:8081

# 3. Check logs của Silver transformation
# → Airflow UI → lakehouse_pipeline_taskflow → run_silver_transformation → Logs
```

**4. MLflow empty (no models)**

**Nguyên nhân:** Training job chưa chạy hoặc fail do insufficient data

**Giải pháp:**

```bash
# 1. Verify Silver có data (cần ít nhất 1000 records)
docker exec -it trino trino --execute "SELECT COUNT(*) FROM hive.silver.transactions WHERE amt > 0"

# 2. Trigger training DAG manually
# Airflow UI → model_retraining_taskflow → Trigger DAG

# 3. Check training logs
# Airflow UI → model_retraining_taskflow → train_ml_models → Logs
```

**5. Debezium amt field = NULL (Base64 encoding)**

**Nguyên nhân:** Debezium mặc định encode NUMERIC/DECIMAL as Base64

**Giải pháp:** Connector đã fix với `decimal.handling.mode=double` trong `deployment/debezium/setup-connector.sh`

**Verify fix:**

```bash
# Check Kafka message format
docker exec kafka kafka-console-consumer --bootstrap-server localhost:9092 --topic postgres.public.transactions --max-messages 1
```

**Output đúng:** `"amt": 23.45` (plain double, không phải `"amt": "AfE="`)

**📖 Chi tiết:** Xem [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md) cho 15+ issues khác
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
├── bronze/transactions/ # Raw CDC data (Debezium format parsed)
│ └── \_delta_log/ # Delta Lake transaction logs
├── silver/transactions/ # 40 engineered features
│ └── \_delta_log/
├── gold/ # Star Schema (5 tables)
│ ├── dim_customer/
│ ├── dim_merchant/
│ ├── dim_time/
│ ├── dim_location/
│ └── fact_transactions/
├── checkpoints/ # Spark streaming checkpoints
│ ├── kafka_to_bronze/ # Bronze streaming state
│ ├── bronze_to_silver_batch/ # Silver batch watermark
│ └── silver_to_gold_batch/ # Gold batch watermark
└── models/ # ML models & artifacts (future)

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
↓ Hive Metastore (Auto-registration every 1 hour)
↓ Trino Query Engine (Delta Catalog via Hive Metastore)
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

| Service             | URL                   | Credentials            | Purpose                                  |
| ------------------- | --------------------- | ---------------------- | ---------------------------------------- |
| Spark Master UI     | http://localhost:8080 | None                   | Monitor Spark jobs & resource allocation |
| MinIO Console       | http://localhost:9001 | minio / minio123       | S3-compatible Data Lake storage          |
| Trino UI            | http://localhost:8085 | None                   | Distributed SQL query engine             |
| Metabase            | http://localhost:3000 | (setup on first visit) | BI Dashboard & visualization             |
| MLflow UI           | http://localhost:5000 | None                   | ML model tracking & registry             |
| Kafka UI            | http://localhost:9002 | None                   | Kafka topics & messages monitoring       |
| Fraud Detection API | http://localhost:8000 | None                   | Real-time prediction endpoint (future)   |
| Kafka Broker        | localhost:9092        | None                   | Message streaming platform               |
| PostgreSQL          | localhost:5432        | postgres / postgres    | Source database (frauddb)                |
| Hive Metastore      | localhost:9083        | None (Thrift)          | Table metadata store for Trino           |

---

### 11. Key Features & Achievements

✅ **Hybrid Architecture**: Streaming (Bronze) + Batch (Silver/Gold) for optimal CPU usage
✅ **Real-time CDC**: Debezium captures INSERT/UPDATE/DELETE from PostgreSQL
✅ **ACID Transactions**: Delta Lake ensures data consistency
✅ **Incremental Processing**: Only process new data (watermark-based)
✅ **Schema Evolution**: Support for ancient dates with LEGACY mode
✅ **40 Features**: Geographic, demographic, time-based, amount-based
✅ **Star Schema**: 4 dimensions + 1 fact table for analytics
✅ **Trino Query Engine**: Delta connector queries directly from `_delta_log/` + MinIO
✅ **Metadata Cache**: Hive Metastore speeds up `SHOW TABLES` (~100ms vs ~1-2s)
✅ **Auto Registration**: Tables auto-register to Metastore via Airflow
✅ **Metabase Ready**: Pre-configured for BI dashboards (Delta catalog)
✅ **60% CPU Reduction**: From 300%+ to ~195% by moving to batch processing

### 12. Understanding Hive Metastore Role

**❓ Tại sao cần Hive Metastore nếu Delta Lake tự quản lý metadata?**

| Aspect | Delta Lake (_delta_log/) | Hive Metastore |
|--------|-------------------------|----------------|
| **Primary role** | Data storage + transaction logs | Metadata cache |
| **Query data** | ✅ YES (via Delta connector) | ❌ NO (Hive connector cannot read Delta) |
| **List tables** | ✅ YES (~1-2s, scan S3) | ✅ YES (~100ms, cache hit) |
| **SHOW SCHEMAS** | ✅ YES (slow) | ✅ YES (fast) |
| **Required?** | ✅ MANDATORY | ⚠️ OPTIONAL (performance optimization) |

**🎯 Kết luận:**
- **Hive Metastore = Metadata cache** (giúp discovery nhanh hơn 10-20x)
- **Delta connector = Query engine** (đọc trực tiếp từ `_delta_log/` + S3)
- **Có thể bỏ Hive?** CÓ - nhưng `SHOW TABLES` sẽ chậm hơn
- **Nên giữ?** NÊN - setup đã tối ưu, không tốn nhiều resources (~300MB RAM)

**📚 Chi tiết:** Xem [`docs/HIVE_METASTORE_ROLE.md`](docs/HIVE_METASTORE_ROLE.md)

---

## Chi tiết kỹ thuật

Xem file `docs/PROJECT_SPECIFICATION.md` để hiểu rõ:

- Kiến trúc hệ thống chi tiết
- Yêu cầu nghiệp vụ
- Data flow và processing layers
- ML pipeline specifications

## Additional Documentation

- **[METABASE_SETUP.md](docs/METABASE_SETUP.md)** - Metabase connection guide (Delta catalog) + 7 sample fraud detection queries
- **[HIVE_METASTORE_ROLE.md](docs/HIVE_METASTORE_ROLE.md)** - ⭐ **Giải thích vai trò Hive Metastore** (metadata cache vs query engine)
- **[HIVE_TRINO_FIX.md](docs/HIVE_TRINO_FIX.md)** - Hive Metastore setup fixes + Trino CLI usage
- **[TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)** - Detailed solutions for 6 major issues encountered during setup
- **[PROJECT_SPECIFICATION.md](docs/PROJECT_SPECIFICATION.md)** - Full architecture specifications and requirements
- **[IMPLEMENTATION_PLAN_A.md](docs/IMPLEMENTATION_PLAN_A.md)** - Hybrid architecture implementation details
```
