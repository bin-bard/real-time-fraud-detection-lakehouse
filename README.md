# Real-Time Fraud Detection Lakehouse

Hệ thống Data Lakehouse phát hiện gian lận thẻ tín dụng theo thời gian thực sử dụng **Delta Lake** + **Apache Spark** + **Trino**.

## 🎯 Tổng quan

Dự án xây dựng pipeline xử lý dữ liệu end-to-end từ CDC (Change Data Capture) đến Analytics Dashboard:

- **Real-time CDC**: PostgreSQL → Debezium → Kafka → Bronze (Streaming)
- **Batch ETL**: Bronze → Silver → Gold (Airflow mỗi 5 phút)
- **ML Training**: RandomForest + LogisticRegression (Airflow hàng ngày 2 AM)
- **Analytics**: Trino + Metabase Dashboard

## 🛠️ Tech Stack

| Component         | Technology           | Port       | Mô tả                           |
| ----------------- | -------------------- | ---------- | ------------------------------- |
| **Source DB**     | PostgreSQL 14        | 5432       | OLTP database với CDC enabled   |
| **CDC**           | Debezium 2.5         | 8083       | Change Data Capture             |
| **Streaming**     | Apache Kafka         | 9092       | Message broker                  |
| **Processing**    | Spark 3.4.1          | 8080       | Stream & batch processing       |
| **Storage**       | Delta Lake + MinIO   | 9000, 9001 | ACID lakehouse                  |
| **Metastore**     | Hive Metastore 3.1.3 | 9083       | Metadata cache (optional)       |
| **Query**         | Trino                | 8085       | Distributed SQL engine          |
| **Orchestration** | Airflow 2.8.0        | 8081       | Workflow scheduling             |
| **ML Tracking**   | MLflow 2.8.0         | 5000       | Model tracking                  |
| **Visualization** | Metabase             | 3000       | BI dashboard                    |
| **API**           | FastAPI              | 8000       | Real-time prediction (optional) |

## 📋 Yêu cầu hệ thống

**Phần cứng:**

- CPU: 6 cores minimum (khuyến nghị 8+)
- RAM: 10GB minimum (khuyến nghị 16GB)
- Disk: 30GB free space

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

## 🚀 Hướng dẫn chạy

### 1. Clone repository

```bash
git clone https://github.com/bin-bard/real-time-fraud-detection-lakehouse.git
cd real-time-fraud-detection-lakehouse
```

### 2. Khởi động hệ thống

```bash
docker compose up -d --build
```

**⏳ Thời gian khởi động:** ~5-10 phút (tải images + khởi tạo services)

### 3. Bulk load initial data (Optional - Khuyến nghị)

Để có đủ data cho ML training ngay lập tức:

```bash
# Load 50K transactions (~250 fraud samples)
docker exec data-producer python producer.py --bulk-load 50000
```

**Kết quả:**

- ~50K records trong 2-3 phút
- ~250 fraud transactions (0.5% fraud rate)
- Đủ data cho ML training ngay
- Producer tự động tiếp tục streaming sau khi xong

**Checkpoint safe:** Không duplicate records, resume đúng vị trí sau khi restart.

### 4. Verify hệ thống

#### Check services đang chạy

```bash
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

**Mong đợi:** 15+ containers với status `Up`

#### Check Bronze streaming

```bash
docker logs bronze-streaming --tail 20
```

**Mong đợi:**

```
Batch 5 processing started
Writing 142 records to Bronze layer...
✅ Batch 5 written successfully
```

#### Check Airflow DAG

- Truy cập: http://localhost:8081 (`admin` / `admin`)
- DAG: `lakehouse_pipeline_taskflow` (mỗi 5 phút)
- Verify: Silver/Gold tasks thành công

#### Check data trong MinIO

- Truy cập: http://localhost:9001 (`minio` / `minio123`)
- Bucket: `lakehouse`
- Verify folders: `bronze/`, `silver/`, `gold/`

#### Query data qua Trino

```bash
docker exec -it trino trino --server localhost:8081
```

```sql
-- Verify data tồn tại
SELECT COUNT(*) FROM delta.bronze.transactions;
SELECT COUNT(*) FROM delta.silver.transactions;
SELECT COUNT(*) FROM delta.gold.fact_transactions;

-- Sample data
SELECT * FROM delta.gold.fact_transactions LIMIT 5;

-- Fraud distribution
SELECT is_fraud, COUNT(*) as count
FROM delta.silver.transactions
GROUP BY is_fraud;

quit;
```

**⚠️ QUAN TRỌNG:** Query data phải dùng **`delta`** catalog (KHÔNG dùng `hive`):

- ✅ `delta.bronze.*`, `delta.silver.*`, `delta.gold.*`
- ❌ `hive.*` (chỉ list tables, không query được Delta format)

## 🔑 Access Services

| Service             | URL                   | Username / Password | Ghi chú                                    |
| ------------------- | --------------------- | ------------------- | ------------------------------------------ |
| **Airflow**         | http://localhost:8081 | `admin` / `admin`   | Workflow orchestration                     |
| **Spark Master UI** | http://localhost:8080 | -                   | Monitoring Spark jobs                      |
| **MinIO Console**   | http://localhost:9001 | `minio` / `minio123`| Data Lake storage                          |
| **MLflow UI**       | http://localhost:5000 | -                   | ML model tracking                          |
| **Kafka UI**        | http://localhost:9002 | -                   | Topics, messages, consumer groups          |
| **Trino UI**        | http://localhost:8085 | -                   | Query engine monitoring                    |
| **Metabase**        | http://localhost:3000 | (tạo admin lần đầu) | BI Dashboard                               |
| **PostgreSQL**      | localhost:5432        | `postgres` / `postgres` | Source database                        |

## 📊 Kiến trúc hệ thống

### Medallion Architecture (Hybrid: Streaming + Batch)

```
PostgreSQL (Source)
    ↓ Debezium CDC
Kafka (postgres.public.transactions)
    ↓ Bronze Streaming (Continuous, ~195% CPU)
Bronze Delta Lake (s3a://lakehouse/bronze/)
    ↓ Silver Batch (Every 5 minutes via Airflow)
Silver Delta Lake (s3a://lakehouse/silver/)
    ↓ Gold Batch (Every 5 minutes via Airflow)
Gold Delta Lake (s3a://lakehouse/gold/) - 5 tables
    ↓
Trino Delta Catalog (Query data)
    ↓
Metabase/DBeaver (Analytics)
```

**Lớp dữ liệu:**

1. **Bronze** - Raw CDC data (real-time streaming)
2. **Silver** - Cleaned + Feature engineering (batch mỗi 5 phút)
3. **Gold** - Star Schema: 4 dimensions + 1 fact table (batch mỗi 5 phút)

**Gold Layer Tables:**

- `dim_customer` - Customer dimension
- `dim_merchant` - Merchant dimension
- `dim_time` - Time dimension
- `dim_location` - Location dimension
- `fact_transactions` - Transaction facts (25K+ records)

## 🤖 ML Training

### Automated Training (Airflow)

- **Schedule:** Daily at 2 AM
- **DAG:** `model_retraining_taskflow`
- **Models:** RandomForest + LogisticRegression
- **Metrics:** Accuracy, Precision, Recall, F1, AUC

### Manual Trigger

Airflow UI → `model_retraining_taskflow` → ▶️ Trigger DAG

### Resource Management

**Trước khi chạy ML training:**

```powershell
# Giải phóng ~2GB RAM + 1-2 CPU cores
.\scripts\prepare-ml-training.ps1
```

**Sau khi training xong:**

```powershell
# Khôi phục services
.\scripts\restore-services.ps1
```

### Verify models

- Truy cập: http://localhost:5000
- Experiment: `fraud_detection_production`
- Check runs: RandomForest, LogisticRegression

### Training samples FAQ

**Q: Tại sao chỉ có ~15-20 training samples?**

**A:** Đây là behavior ĐÚNG với real-world fraud detection!

| Metric                  | Value       | Explanation                |
| ----------------------- | ----------- | -------------------------- |
| Total records (Silver)  | ~4,200      | Sau vài phút streaming     |
| Fraud transactions      | ~10 (0.24%) | Real-world fraud rate 0.5% |
| After class balancing   | 10 + 10 = 20| Undersample majority 1:1   |
| Train/Test split (80/20)| 16 + 4      | Final dataset              |

**Giải pháp:** Bulk load 50K records → ~250 fraud samples → better training

```bash
docker exec data-producer python producer.py --bulk-load 50000
```

## 🔧 Kết nối Metabase

### Database Configuration

```yaml
Database Type: Trino
Display Name: Fraud Detection Lakehouse

Connection:
  Host: trino         # Nếu Metabase chạy trong Docker
  # Host: localhost   # Nếu Metabase chạy ngoài Docker
  Port: 8081          # Internal port (8085 for external)
  Catalog: delta      # ⚠️ IMPORTANT: Dùng delta, không phải hive
  Database: gold      # Hoặc 'silver'/'bronze'

Authentication:
  Username: (leave empty)
  Password: (leave empty)
```

### Sample Queries

```sql
-- Fraud rate by category
SELECT
    transaction_category,
    COUNT(*) as total_transactions,
    SUM(CASE WHEN is_fraud = 1 THEN 1 ELSE 0 END) as fraud_count,
    ROUND(100.0 * SUM(CASE WHEN is_fraud = 1 THEN 1 ELSE 0 END) / COUNT(*), 2) as fraud_rate
FROM delta.gold.fact_transactions
GROUP BY transaction_category
ORDER BY fraud_rate DESC

-- Top 10 high-risk merchants
SELECT
    merchant_name,
    merchant_category,
    COUNT(*) as total_transactions,
    SUM(CASE WHEN is_fraud = 1 THEN 1 ELSE 0 END) as fraud_count
FROM delta.gold.fact_transactions
GROUP BY merchant_name, merchant_category
HAVING COUNT(*) > 10
ORDER BY fraud_count DESC
LIMIT 10
```

## 🔧 Kết nối DBeaver/SQL Client

**JDBC URL:**

```
jdbc:trino://localhost:8085/delta
```

**Connection Settings:**

- Host: `localhost`
- Port: `8085`
- Database/Catalog: `delta`
- Schema: `gold` (hoặc `silver`, `bronze`)
- Username: `trino` (hoặc bất kỳ)
- Password: (để trống)

## 🐛 Troubleshooting

### High CPU usage (>500%)

**Bình thường:**

- `bronze-streaming`: ~195% CPU (continuous)
- `spark-master`: ~50-100% CPU khi chạy job
- `airflow-*`: ~10-30% CPU

**Nếu >600%:** Restart services

```bash
docker compose restart bronze-streaming spark-master spark-worker
```

### No data in Silver/Gold

```bash
# 1. Check Bronze có data
docker exec trino trino --server localhost:8081 --execute "SELECT COUNT(*) FROM delta.bronze.transactions"

# 2. Check Airflow DAG đang chạy
# Airflow UI: http://localhost:8081 → lakehouse_pipeline_taskflow

# 3. Check logs
docker logs airflow-scheduler --tail 50
```

### MLflow empty (no models)

```bash
# 1. Verify Silver có đủ data (cần ít nhất 1000 records với fraud samples)
docker exec trino trino --server localhost:8081 --execute "SELECT is_fraud, COUNT(*) FROM delta.silver.transactions GROUP BY is_fraud"

# 2. Trigger training DAG
# Airflow UI → model_retraining_taskflow → Trigger DAG

# 3. Check logs
# Airflow UI → model_retraining_taskflow → train_ml_models → Logs
```

### Reset toàn bộ hệ thống

```bash
# ⚠️ Cảnh báo: Xóa toàn bộ data!
docker compose down -v
docker compose up -d --build
```

## 📖 Documentation

- **[PROJECT_SPECIFICATION.md](docs/PROJECT_SPECIFICATION.md)** - Đặc tả chi tiết architecture, data flow, requirements
- **[CHANGELOG.md](docs/CHANGELOG.md)** - Lịch sử cập nhật, lỗi đã sửa, FAQ

## 📝 License

MIT License - Nhóm 6, GVHD: ThS. Phan Thị Thể

## 👥 Contributors

- Nguyễn Thanh Tài - 22133049
- Võ Triệu Phúc - 22133043
