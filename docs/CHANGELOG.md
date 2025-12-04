# CHANGELOG & TROUBLESHOOTING

Ghi lại lịch sử phát triển, lỗi đã sửa, cập nhật và câu hỏi thường gặp.

---

## 📅 Lịch sử phiên bản

### v6.0 - Final Implementation (4 tháng 12, 2025)

**✅ Tính năng hoàn thành:**

- Real-time CDC pipeline (PostgreSQL → Kafka → Delta Lake)
- Hybrid processing (Streaming Bronze + Batch Silver/Gold)
- Automated ML training (RandomForest + LogisticRegression)
- Airflow orchestration (2 DAGs)
- MLflow experiment tracking
- Trino query engine với Delta catalog
- Bulk load feature cho initial data
- **FastAPI prediction service** với MLflow integration

**🔧 Sửa lỗi chính:**

- Debezium NUMERIC encoding (Base64 → double)
- Hive Metastore restart issue (schema conflict)
- Trino port confusion (8080 → 8081)
- ML training sample size explanation
- Data producer checkpoint recovery
- FastAPI deployment với hot model reload

---

## 🐛 Các lỗi đã sửa & Giải pháp

### Lỗi #1: Debezium field `amt` trả về NULL

**Ngày phát hiện:** 28 tháng 11, 2025

**Triệu chứng:**

- Kafka messages có `"amt": "AfE="` (Base64 encoded)
- Bronze layer: `amt = NULL`
- Silver/Gold layer: Không có dữ liệu số tiền

**Nguyên nhân gốc:**

Debezium mặc định encode NUMERIC/DECIMAL fields dạng **Base64** để preserve precision. Spark không tự động decode Base64.

**Giải pháp:**

Cấu hình Debezium connector với `decimal.handling.mode=double`:

```json
{
  "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
  "decimal.handling.mode": "double",
  ...
}
```

**File đã sửa:** `deployment/debezium/setup-connector.sh`

**Kiểm tra:**

```bash
# Check Kafka message format
docker exec kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic postgres.public.transactions \
  --max-messages 1

# ✅ Mong đợi: "amt": 23.45 (plain double)
# ❌ Trước đây: "amt": "AfE=" (Base64)
```

**Trạng thái:** ✅ Đã giải quyết

---

### Lỗi #2: Hive Metastore không khởi động lại được

**Ngày phát hiện:** 30 tháng 11, 2025

**Triệu chứng:**

```
ERROR: relation "BUCKETING_COLS" already exists
FATAL: database system is corrupted
```

Container crash loop mỗi khi restart.

**Nguyên nhân gốc:**

- Hive Metastore init script (`schematool -initSchema`) chạy mỗi lần start
- PostgreSQL volume giữ schema → schema đã tồn tại
- Init script cố tạo lại schema → conflict

**Giải pháp 1 (ban đầu):** Xóa volume persistence

```yaml
# ❌ CŨ - Gây lỗi:
metastore-db:
  volumes:
    - metastore_db:/var/lib/postgresql/data

# ✅ MỚI - No persistence:
metastore-db:
  # Không có volumes - fresh DB mỗi lần start
```

**Giải pháp 2 (cuối cùng):** Custom entrypoint với schema check

**File:** `deployment/hive-metastore/entrypoint.sh`

```bash
#!/bin/bash
set -e

# Wait for PostgreSQL
until pg_isready -h metastore-db -U hive; do
  echo "Waiting for PostgreSQL..."
  sleep 2
done

# Check if schema exists
SCHEMA_EXISTS=$(psql -h metastore-db -U hive -d metastore -tAc \
  "SELECT 1 FROM information_schema.tables WHERE table_name='BUCKETING_COLS'" || echo "0")

if [ "$SCHEMA_EXISTS" = "1" ]; then
  echo "✅ Schema already exists, skipping init"
else
  echo "🔧 Initializing schema..."
  /opt/hive/bin/schematool -dbType postgres -initSchema
fi

# Start Hive Metastore
exec /opt/hive/bin/hive --service metastore
```

**Files đã sửa:**

- `deployment/hive-metastore/Dockerfile` - COPY entrypoint.sh
- `docker-compose.yml` - Bật lại volume persistence

**Trạng thái:** ✅ Đã giải quyết

---

### Lỗi #3: Hadoop Version Mismatch

**Ngày phát hiện:** 30 tháng 11, 2025

**Triệu chứng:**

```
java.lang.ClassNotFoundException: org.apache.hadoop.fs.s3a.S3AFileSystem
java.lang.NoSuchMethodError: org.apache.hadoop.fs.statistics.IOStatisticsSource.getIOStatistics()
```

**Nguyên nhân gốc:**

- Hive 3.1.3 build với Hadoop 3.1.0
- Custom JARs dùng Hadoop 3.3.4
- API incompatibility giữa 3.1.0 và 3.3.4

**Giải pháp:**

Downgrade JARs về compatible versions:

```bash
# deployment/hive-metastore/lib/
hadoop-aws-3.1.0.jar              # ← Từ 3.3.4
aws-java-sdk-bundle-1.11.375.jar  # ← Từ 1.12.262

# XÓA các JARs conflict:
# hadoop-common-3.3.4.jar
# hadoop-shaded-guava-*.jar
```

**File đã sửa:** `deployment/hive-metastore/lib/` directory

**Trạng thái:** ✅ Đã giải quyết

---

### Lỗi #4: MinIO Credential Mismatch (403 Forbidden)

**Ngày phát hiện:** 30 tháng 11, 2025

**Triệu chứng:**

```
Status Code: 403, AWS Service: Amazon S3
AWS Error Message: Forbidden
```

**Nguyên nhân gốc:**

- MinIO service: `minio` / `minio123`
- Hive core-site.xml: `minioadmin` / `minioadmin`

**Giải pháp:**

Cập nhật credentials trong `core-site.xml`:

```xml
<property>
  <name>fs.s3a.access.key</name>
  <value>minio</value>  <!-- ← Từ minioadmin -->
</property>

<property>
  <name>fs.s3a.secret.key</name>
  <value>minio123</value>  <!-- ← Từ minioadmin -->
</property>
```

**File đã sửa:** `deployment/hive-metastore/core-site.xml`

**Trạng thái:** ✅ Đã giải quyết

---

### Lỗi #5: MSCK REPAIR TABLE Not Supported

**Ngày phát hiện:** 1 tháng 12, 2025

**Triệu chứng:**

```
ERROR: MSCK REPAIR TABLE is not supported for v2 tables
```

Chỉ 2/7 tables đăng ký thành công.

**Nguyên nhân gốc:**

- Delta Lake v2 sử dụng `_delta_log/` transaction log
- `MSCK REPAIR TABLE` chỉ cho Hive partitioned tables (Parquet/ORC)
- Delta tự động quản lý partitions

**Giải pháp:**

Xóa lệnh MSCK REPAIR:

```python
# spark/app/register_tables_to_hive.py

# ❌ CŨ (dòng 63):
spark.sql(f"MSCK REPAIR TABLE {database}.{table_name}")

# ✅ MỚI (dòng 63-64):
# Note: MSCK REPAIR TABLE not supported for Delta v2 tables
# Delta tự động quản lý partitions qua _delta_log/
```

**Kiểm tra:**

```bash
docker logs hive-registration --tail 50

# ✅ Mong đợi:
# Registered bronze.transactions (25,000 records)
# Registered silver.transactions (25,000 records)
# Registered gold.dim_customer
# ...tất cả 7 tables
```

**Trạng thái:** ✅ Đã giải quyết

---

### Lỗi #6: Trino Port Confusion (Connection Refused)

**Ngày phát hiện:** 1 tháng 12, 2025

**Triệu chứng:**

```
java.net.ConnectException: Failed to connect to localhost:8080
```

**Nguyên nhân gốc:**

- Trino internal port: **8081**
- Trino external port: **8085**
- Default `trino` CLI giả định port 8080

**Giải pháp:**

Luôn chỉ định port rõ ràng:

```bash
# ✅ Bên trong Docker network:
docker exec trino trino --server localhost:8081

# ✅ Từ host machine:
trino --server localhost:8085

# ❌ Sai (mặc định 8080):
docker exec trino trino
```

**Cấu hình Metabase:**

```yaml
Host: trino # Docker service name
Port: 8081 # Internal port
```

**Trạng thái:** ✅ Đã giải quyết

---

### Lỗi #7: ML Training với ít samples (~15-20)

**Ngày phát hiện:** 3 tháng 12, 2025

**Triệu chứng:**

MLflow UI hiển thị:

- `train_samples: 14-17`
- `test_samples: 3-4`

User có 4000+ records trong Silver nhưng chỉ 20 samples.

**Nguyên nhân gốc:**

**ĐÂY KHÔNG PHẢI LỖI!** Hành vi real-world fraud detection:

| Metric                | Giá trị     | Giải thích             |
| --------------------- | ----------- | ---------------------- |
| Tổng records Silver   | ~4,200      | Sau vài phút streaming |
| Giao dịch gian lận    | ~10 (0.24%) | Tỉ lệ thực tế: 0.5-1%  |
| Giao dịch bình thường | ~4,190      | Majority class         |
| **Sau class balance** | 10+10=20    | Undersample tỉ lệ 1:1  |
| Train/Test (80/20)    | 16 + 4      | Dataset cuối cùng      |

**Giải pháp:**

**Tùy chọn 1: Bulk Load (Khuyến nghị)**

```bash
# Load 50K transactions → ~250 fraud samples
docker exec data-producer python producer.py --bulk-load 50000
```

**Tùy chọn 2: Đợi tự nhiên**

- Tỉ lệ fraud 0.5% → 100 frauds cần ~20K transactions
- Data producer streaming: ~5-10 transactions/giây
- Đợi ~2-4 giờ để có đủ dữ liệu

**Tùy chọn 3: Tăng tốc streaming**

```python
# Sửa services/data-producer/producer.py
time.sleep(0.5)  # Thay vì time.sleep(5)
```

**Documentation đã cập nhật:**

- `README.md` - Thêm bulk load feature
- `docs/TROUBLESHOOTING.md` - Thêm giải thích Issue #7

**Trạng thái:** ✅ Không phải lỗi - Hoạt động đúng thiết kế

---

### Lỗi #8: MLflow Verification Task Failed

**Ngày phát hiện:** 3 tháng 12, 2025

**Triệu chứng:**

Airflow task `verify_mlflow` failed với "Models not found in registry"

**Nguyên nhân gốc:**

- Task kiểm tra MLflow **Model Registry** (registered models cho production)
- Nhưng training log vào **MLflow Tracking** (experiments/runs)
- Hai khái niệm khác nhau trong MLflow!

**Giải pháp:**

Cập nhật verification task kiểm tra **Tracking** thay vì **Registry**:

```python
# airflow/dags/model_retraining_taskflow.py

# ✅ MỚI - Kiểm tra MLflow Tracking (experiments/runs)
response = requests.get(
    "http://mlflow:5000/api/2.0/mlflow/experiments/search"
)
experiments = response.json().get("experiments", [])

# Tìm experiment
fraud_exp = next(
    (e for e in experiments if e["name"] == "fraud_detection_production"),
    None
)

# Kiểm tra runs
runs_response = requests.get(
    f"http://mlflow:5000/api/2.0/mlflow/runs/search",
    json={"experiment_ids": [fraud_exp["experiment_id"]]}
)
```

**Cũng đã sửa:** Đổi từ `curl` sang Python `requests` (mlflow container thiếu curl)

**Trạng thái:** ✅ Đã giải quyết

---

### Lỗi #9: FastAPI không load được model từ MLflow

**Ngày phát hiện:** 4 tháng 12, 2025

**Triệu chứng:**

```
ModuleNotFoundError: No module named 'mlflow'
WARNING: Model not loaded, using rule-based prediction
```

**Nguyên nhân gốc:**

- FastAPI service chưa được deploy trong `docker-compose.yml`
- Code đã có nhưng container không chạy
- Lỗi import chỉ là IDE warning (không phải lỗi runtime)

**Giải pháp:**

1. **Thêm service vào docker-compose.yml:**

```yaml
fraud-detection-api:
  build: ./services/fraud-detection-api
  container_name: fraud-detection-api
  ports:
    - "8000:8000"
  environment:
    MLFLOW_TRACKING_URI: http://mlflow:5000
    AWS_ACCESS_KEY_ID: minio
    AWS_SECRET_ACCESS_KEY: minio123
    MLFLOW_S3_ENDPOINT_URL: http://minio:9000
    MODEL_NAME: fraud_detection_randomforest
    MODEL_STAGE: None
  depends_on:
    - mlflow
    - minio
  networks:
    - data_network
  restart: unless-stopped
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
    interval: 30s
    timeout: 10s
    retries: 3
```

2. **Upgrade main.py với MLflow integration:**

```python
def load_model_from_mlflow():
    """Load model từ MLflow Registry hoặc latest run"""
    try:
        # Ưu tiên: Model Registry
        model_uri = f"models:/{MODEL_NAME}/{MODEL_STAGE}"
        loaded_model = mlflow.pyfunc.load_model(model_uri)

    except Exception as e:
        # Fallback: Latest experiment run
        runs = client.search_runs(
            experiment_ids=[experiment.experiment_id],
            filter_string="tags.model_type='RandomForest'",
            order_by=["start_time DESC"],
            max_results=1
        )
        run = runs[0]
        model_uri = f"runs:/{run.info.run_id}/model"
        loaded_model = mlflow.pyfunc.load_model(model_uri)
```

3. **Cập nhật Dockerfile với curl:**

```dockerfile
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*
```

**Kiểm tra:**

```bash
# Build và start service
docker compose up -d --build fraud-detection-api

# Test health
curl http://localhost:8000/health

# Test prediction
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"amt": 850.50, "log_amount": 6.75, ...}'
```

**Trạng thái:** ✅ Đã giải quyết

---

## ❓ Câu hỏi thường gặp (FAQ)

### Q1: Hive Metastore có vai trò gì?

**A:** Hive Metastore là **metadata cache** (KHÔNG phải query engine):

- ✅ Tăng tốc `SHOW TABLES` (~100ms vs ~1-2s)
- ✅ Compatibility với BI tools cũ
- ❌ KHÔNG dùng để query data
- ❌ KHÔNG bắt buộc (Delta tự discover tables)

**Mẫu truy vấn:**

```sql
-- ✅ ĐÚNG - Query data
SELECT * FROM delta.gold.fact_transactions;

-- ✅ OK - List metadata
SHOW TABLES FROM hive.gold;

-- ❌ SAI - Query qua Hive
-- SELECT * FROM hive.gold.fact_transactions; -- Error!
```

---

### Q2: Tại sao không dùng `hive.*` catalog để query?

**A:** Hive connector không hiểu Delta format:

- Delta Lake sử dụng `_delta_log/` transaction log
- Hive connector chỉ đọc Parquet/ORC thuần
- Trino's **Delta connector** đọc trực tiếp từ Delta format

**Khi nào dùng Hive catalog?**

- SHOW TABLES (metadata discovery)
- Query non-Delta tables (Parquet/ORC thuần)

**Khi nào dùng Delta catalog?**

- Query Delta Lake tables (PHẢI dùng!)
- Tất cả SELECT/INSERT/UPDATE operations

---

### Q3: Producer tắt rồi bật lại có bị lỗi không?

**A:** KHÔNG - nhờ checkpoint mechanism:

```python
# services/data-producer/producer.py

# 1. Đọc checkpoint từ PostgreSQL
last_line = get_last_checkpoint()

# 2. Resume từ dòng cuối cùng
for i, row in enumerate(reader, start=last_line + 1):
    # Process...
    save_checkpoint(i, row['trans_num'])
```

**Checkpoint table:**

```sql
CREATE TABLE producer_checkpoint (
    id INT PRIMARY KEY,
    last_line_processed INT,
    last_trans_num VARCHAR(255),
    updated_at TIMESTAMP
);
```

**An toàn:**

- ✅ Không duplicate records
- ✅ Resume đúng vị trí
- ✅ Bulk load cũng tuân theo checkpoint

---

### Q4: Bulk load có conflict với streaming không?

**A:** KHÔNG conflict:

**Cơ chế:**

1. Bulk load insert vào PostgreSQL
2. Debezium capture INSERT events → Kafka
3. Bronze streaming xử lý events
4. Silver/Gold batch process sau 5 phút
5. Producer tiếp tục streaming từ dòng tiếp theo

**Checkpoint safe:**

- PostgreSQL SERIAL primary key (auto-increment)
- Debezium LSN (Log Sequence Number)
- Spark streaming checkpoint (exactly-once)

---

### Q5: Làm sao biết hệ thống đang chạy tốt?

**A:** Kiểm tra các chỉ số sau:

**1. Container health:**

```bash
docker ps --format "table {{.Names}}\t{{.Status}}"
# Tất cả containers: Up (healthy)
```

**2. Bronze streaming:**

```bash
docker logs bronze-streaming --tail 20
# ✅ "Batch X written successfully"
```

**3. Airflow DAGs:**

- http://localhost:8081
- `lakehouse_pipeline_taskflow`: Success (xanh)
- Recent runs: < 5 phút trước

**4. Số lượng dữ liệu:**

```sql
-- Trino query
SELECT
  'bronze' as layer, COUNT(*) FROM delta.bronze.transactions
UNION ALL
SELECT 'silver', COUNT(*) FROM delta.silver.transactions
UNION ALL
SELECT 'gold', COUNT(*) FROM delta.gold.fact_transactions;

-- ✅ Số lượng tương đương (bronze ≈ silver ≈ gold)
```

**5. CPU usage:**

```bash
docker stats --no-stream

# ✅ Bình thường:
# bronze-streaming: ~195% CPU (continuous)
# spark-master: ~50-100% CPU (when running jobs)
# airflow-*: ~10-30% CPU
```

---

### Q6: Khi nào nên restart services?

**A:** Chỉ restart khi:

1. **High CPU (>600% total)**: Spark jobs stuck
2. **Out of memory**: Container crash loop
3. **No data flow**: Bronze/Silver/Gold không cập nhật
4. **Config changes**: Thay đổi docker-compose.yml

**Lệnh restart:**

```bash
# Restart service cụ thể
docker compose restart bronze-streaming

# Restart tất cả Spark services
docker compose restart spark-master spark-worker bronze-streaming

# Full restart (giữ data)
docker compose down
docker compose up -d

# Nuclear option (xóa TẤT CẢ data)
docker compose down -v
docker compose up -d --build
```

---

### Q7: Data producer chạy bao lâu?

**A:** Tùy mode:

**Streaming mode (mặc định):**

- Chạy vô thời hạn (container restart: always)
- Insert ~5-10 transactions/giây
- Fraud rate: 0.5-1%
- Dataset size: 1.8M records → ~2-4 tuần để hết

**Bulk load mode:**

```bash
docker exec data-producer python producer.py --bulk-load 50000
# → Chạy ~2-3 phút rồi exit
# Producer tự động tiếp tục streaming sau khi bulk load xong
```

---

### Q8: Làm sao backup data?

**A:** Backup 3 thành phần:

**1. MinIO (Data Lake):**

```bash
# Backup bucket
docker exec minio mc mirror lakehouse /backup/lakehouse-$(date +%Y%m%d)

# Restore
docker exec minio mc cp -r /backup/lakehouse-20241204 lakehouse/
```

**2. PostgreSQL (Source + Metastores):**

```bash
# Backup
docker exec postgres pg_dump -U postgres frauddb > backup/frauddb.sql
docker exec airflow-db pg_dump -U airflow airflow > backup/airflow.sql

# Restore
docker exec postgres psql -U postgres < backup/frauddb.sql
```

**3. MLflow artifacts:**

Đã có trong MinIO bucket (`s3a://lakehouse/models/`)

---

### Q9: Metabase không thấy tables?

**A:** Kiểm tra cấu hình connection:

**Lỗi thường gặp:**

```yaml
# ❌ Sai catalog
Catalog: hive # Nên là "delta"

# ❌ Sai port
Port: 8085 # Nên là 8081 (internal) nếu Metabase trong Docker

# ❌ Sai host
Host: localhost # Nên là "trino" nếu Metabase trong Docker
```

**Cấu hình đúng:**

```yaml
Database Type: Trino
Host: trino # Docker service name
Port: 8081 # Internal port
Catalog: delta # ⚠️ PHẢI dùng delta
Database: gold # Hoặc silver/bronze
Username: (để trống)
Password: (để trống)
```

**Kiểm tra Trino hoạt động:**

```bash
docker exec trino trino --server localhost:8081 --execute "SHOW TABLES FROM delta.gold"
# ✅ Nên liệt kê 5 tables
```

---

### Q10: Model training quá lâu?

**A:** Tối ưu tài nguyên:

**Trước khi training:**

```powershell
# Giải phóng ~2GB RAM + 1-2 CPU cores
.\scripts\prepare-ml-training.ps1
```

**Spark config (đã tối ưu):**

```python
'--conf', 'spark.cores.max=2',
'--conf', 'spark.executor.cores=1',
'--conf', 'spark.executor.memory=1g',
'--conf', 'spark.driver.memory=1g',
```

**Thời gian mong đợi:**

- 50K records: ~2-3 phút
- 1M records: ~10-15 phút

**Nếu vẫn chậm:**

- Giảm dataset: Chỉ lọc dữ liệu gần đây
- Tăng resources: Sửa `.wslconfig` (Windows)
- Dùng sampling: Train trên 10% data để test

---

### Q11: FastAPI trả về "model not loaded"?

**A:** Kiểm tra các bước sau:

**1. Service đang chạy?**

```bash
docker ps | grep fraud-detection-api
# ✅ Nên thấy: Up (healthy)
```

**2. Kiểm tra logs:**

```bash
docker logs fraud-detection-api --tail 50

# ✅ Mong đợi:
# "✅ Model loaded successfully from Model Registry"

# ⚠️ Nếu thấy:
# "❌ Failed to load model from MLflow"
# → MLflow chưa có model, chạy training trước
```

**3. Training đã chạy chưa?**

```bash
# Kiểm tra MLflow UI
open http://localhost:5000

# Hoặc trigger manual training
docker exec airflow-scheduler airflow dags trigger model_retraining_taskflow
```

**4. Reload model sau training:**

```bash
curl -X POST http://localhost:8000/model/reload

# ✅ Response:
# {"status": "success", "model_version": "abc123"}
```

**5. Test prediction:**

```bash
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{
    "amt": 850.50,
    "log_amount": 6.75,
    "distance_km": 120.5,
    "age": 35,
    "hour": 23,
    ...
  }'

# ✅ Response:
# {"is_fraud_predicted": 1, "fraud_probability": 0.85, "risk_level": "HIGH"}
```

---

## 🔧 Thao tác thường dùng

### Reset Everything (Clean Slate)

```bash
# ⚠️ CẢNH BÁO: Xóa TẤT CẢ dữ liệu!
docker compose down -v
docker compose up -d --build

# Đợi ~5 phút để khởi tạo
docker logs -f bronze-streaming
```

### Dừng/Khởi động Services (Giữ Data)

```bash
# Dừng (giữ volumes)
docker compose down

# Khởi động
docker compose up -d

# Kiểm tra trạng thái
docker compose ps
```

### Xem Logs

```bash
# Theo dõi logs (Ctrl+C để thoát)
docker logs -f bronze-streaming

# 50 dòng cuối
docker logs bronze-streaming --tail 50

# Lọc theo từ khóa
docker logs airflow-scheduler | grep "ERROR"

# Nhiều services
docker logs bronze-streaming spark-master --tail 20
```

### Dọn dẹp Disk Space

```bash
# Xóa images không dùng
docker image prune -a

# Xóa volumes không dùng
docker volume prune

# Xóa build cache
docker builder prune
```

---

## 📚 Tài nguyên bổ sung

### Vị trí Logs

- Container logs: `docker logs <service-name>`
- Airflow logs: Airflow UI → DAGs → Task → Logs
- Spark logs: http://localhost:8080 → Application → stdout/stderr

### Metrics & Monitoring

- Spark jobs: http://localhost:8080
- Airflow: http://localhost:8081
- MLflow: http://localhost:5000
- Trino: http://localhost:8085
- MinIO: http://localhost:9001
- **FastAPI Docs: http://localhost:8000/docs**

### Files Documentation

- `README.md` - Hướng dẫn nhanh
- `PROJECT_SPECIFICATION.md` - Đặc tả kỹ thuật
- `CHANGELOG.md` - File này (issues, FAQ)

---

**Phiên bản tài liệu:** 1.0  
**Cập nhật lần cuối:** 4 tháng 12, 2025  
**Duy trì bởi:** Nhóm 6
