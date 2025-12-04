# CHANGELOG & TROUBLESHOOTING

Ghi lại lịch sử phát triển, lỗi đã sửa, cập nhật và câu hỏi thường gặp.

---

## 📅 Version History

### v6.0 - Final Implementation (December 4, 2025)

**✅ Completed Features:**

- Real-time CDC pipeline (PostgreSQL → Kafka → Delta Lake)
- Hybrid processing (Streaming Bronze + Batch Silver/Gold)
- Automated ML training (RandomForest + LogisticRegression)
- Airflow orchestration (2 DAGs)
- MLflow experiment tracking
- Trino query engine với Delta catalog
- Bulk load feature cho initial data

**🔧 Major Fixes:**

- Debezium NUMERIC encoding (Base64 → double)
- Hive Metastore restart issue (schema conflict)
- Trino port confusion (8080 → 8081)
- ML training sample size explanation
- Data producer checkpoint recovery

---

## 🐛 Issues Fixed & Resolutions

### Issue #1: Debezium `amt` Field Returns NULL

**Ngày phát hiện:** November 28, 2025

**Triệu chứng:**

- Kafka messages có `"amt": "AfE="` (Base64 encoded)
- Bronze layer: `amt = NULL`
- Silver/Gold layer: Không có dữ liệu số tiền

**Root Cause:**

Debezium mặc định encode NUMERIC/DECIMAL fields as **Base64** để preserve precision. Spark không tự động decode Base64.

**Giải pháp:**

Cấu hình Debezium connector với `decimal.handling.mode=double`:

```json
{
  "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
  "decimal.handling.mode": "double",
  ...
}
```

**File changed:** `deployment/debezium/setup-connector.sh`

**Verification:**

```bash
# Check Kafka message format
docker exec kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic postgres.public.transactions \
  --max-messages 1

# ✅ Expected: "amt": 23.45 (plain double)
# ❌ Before: "amt": "AfE=" (Base64)
```

**Status:** ✅ Resolved

---

### Issue #2: Hive Metastore Fails to Restart

**Ngày phát hiện:** November 30, 2025

**Triệu chứng:**

```
ERROR: relation "BUCKETING_COLS" already exists
FATAL: database system is corrupted
```

Container crash loop mỗi khi restart.

**Root Cause:**

- Hive Metastore init script (`schematool -initSchema`) chạy mỗi lần start
- PostgreSQL volume persist schema → schema đã tồn tại
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

**Giải pháp 2 (final):** Custom entrypoint with schema check

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

**File changed:**

- `deployment/hive-metastore/Dockerfile` - COPY entrypoint.sh
- `docker-compose.yml` - Re-enable volume persistence

**Status:** ✅ Resolved

---

### Issue #3: Hadoop Version Mismatch

**Ngày phát hiện:** November 30, 2025

**Triệu chứng:**

```
java.lang.ClassNotFoundException: org.apache.hadoop.fs.s3a.S3AFileSystem
java.lang.NoSuchMethodError: org.apache.hadoop.fs.statistics.IOStatisticsSource.getIOStatistics()
```

**Root Cause:**

- Hive 3.1.3 built with Hadoop 3.1.0
- Custom JARs used Hadoop 3.3.4
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

**File changed:** `deployment/hive-metastore/lib/` directory

**Status:** ✅ Resolved

---

### Issue #4: MinIO Credential Mismatch (403 Forbidden)

**Ngày phát hiện:** November 30, 2025

**Triệu chứng:**

```
Status Code: 403, AWS Service: Amazon S3
AWS Error Message: Forbidden
```

**Root Cause:**

- MinIO service: `minio` / `minio123`
- Hive core-site.xml: `minioadmin` / `minioadmin`

**Giải pháp:**

Update `core-site.xml` credentials:

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

**File changed:** `deployment/hive-metastore/core-site.xml`

**Status:** ✅ Resolved

---

### Issue #5: MSCK REPAIR TABLE Not Supported

**Ngày phát hiện:** December 1, 2025

**Triệu chứng:**

```
ERROR: MSCK REPAIR TABLE is not supported for v2 tables
```

Chỉ 2/7 tables registered thành công.

**Root Cause:**

- Delta Lake v2 sử dụng `_delta_log/` transaction log
- `MSCK REPAIR TABLE` chỉ cho Hive partitioned tables (Parquet/ORC)
- Delta tự động manage partitions

**Giải pháp:**

Remove MSCK REPAIR command:

```python
# spark/app/register_tables_to_hive.py

# ❌ CŨ (line 63):
spark.sql(f"MSCK REPAIR TABLE {database}.{table_name}")

# ✅ MỚI (line 63-64):
# Note: MSCK REPAIR TABLE not supported for Delta v2 tables
# Delta automatically manages partitions via _delta_log/
```

**Verification:**

```bash
docker logs hive-registration --tail 50

# ✅ Expected:
# Registered bronze.transactions (25,000 records)
# Registered silver.transactions (25,000 records)
# Registered gold.dim_customer
# ...all 7 tables
```

**Status:** ✅ Resolved

---

### Issue #6: Trino Port Confusion (Connection Refused)

**Ngày phát hiện:** December 1, 2025

**Triệu chứng:**

```
java.net.ConnectException: Failed to connect to localhost:8080
```

**Root Cause:**

- Trino internal port: **8081**
- Trino external port: **8085**
- Default `trino` CLI assumes port 8080

**Giải pháp:**

Luôn specify port explicitly:

```bash
# ✅ Inside Docker network:
docker exec trino trino --server localhost:8081

# ✅ From host machine:
trino --server localhost:8085

# ❌ Wrong (defaults to 8080):
docker exec trino trino
```

**Metabase config:**

```yaml
Host: trino # Docker service name
Port: 8081 # Internal port
```

**Status:** ✅ Resolved

---

### Issue #7: ML Training với ít samples (~15-20)

**Ngày phát hiện:** December 3, 2025

**Triệu chứng:**

MLflow UI shows:

- `train_samples: 14-17`
- `test_samples: 3-4`

User có 4000+ records trong Silver nhưng chỉ 20 samples.

**Root Cause:**

**ĐÂY KHÔNG PHẢI LỖI!** Real-world fraud detection behavior:

| Metric                  | Value       | Explanation                 |
| ----------------------- | ----------- | --------------------------- |
| Total Silver records    | ~4,200      | After few minutes streaming |
| Fraud transactions      | ~10 (0.24%) | Real-world rate: 0.5-1%     |
| Non-fraud               | ~4,190      | Majority class              |
| **After class balance** | 10+10=20    | Undersample to 1:1 ratio    |
| Train/Test (80/20)      | 16 + 4      | Final dataset               |

**Giải pháp:**

**Option 1: Bulk Load (Recommended)**

```bash
# Load 50K transactions → ~250 fraud samples
docker exec data-producer python producer.py --bulk-load 50000
```

**Option 2: Wait naturally**

- Fraud rate 0.5% → 100 frauds needs ~20K transactions
- Data producer streaming: ~5-10 transactions/second
- Wait ~2-4 hours for sufficient data

**Option 3: Increase streaming speed**

```python
# Modify services/data-producer/producer.py
time.sleep(0.5)  # Instead of time.sleep(5)
```

**Documentation updated:**

- `README.md` - Added bulk load feature
- `docs/TROUBLESHOOTING.md` - Added Issue #7 explanation

**Status:** ✅ Not a bug - Working as designed

---

### Issue #8: MLflow Verification Task Failed

**Ngày phát hiện:** December 3, 2025

**Triệu chứng:**

Airflow task `verify_mlflow` failed with "Models not found in registry"

**Root Cause:**

- Task checked MLflow **Model Registry** (registered models for production)
- But training logged to **MLflow Tracking** (experiments/runs)
- Two different concepts in MLflow!

**Giải pháp:**

Update verification task to check **Tracking** instead of **Registry**:

```python
# airflow/dags/model_retraining_taskflow.py

# ✅ NEW - Check MLflow Tracking (experiments/runs)
response = requests.get(
    "http://mlflow:5000/api/2.0/mlflow/experiments/search"
)
experiments = response.json().get("experiments", [])

# Find experiment
fraud_exp = next(
    (e for e in experiments if e["name"] == "fraud_detection_production"),
    None
)

# Check runs
runs_response = requests.get(
    f"http://mlflow:5000/api/2.0/mlflow/runs/search",
    json={"experiment_ids": [fraud_exp["experiment_id"]]}
)
```

**Also fixed:** Changed from `curl` to Python `requests` (mlflow container lacks curl)

**Status:** ✅ Resolved

---

## ❓ Frequently Asked Questions

### Q1: Hive Metastore có vai trò gì?

**A:** Hive Metastore là **metadata cache** (KHÔNG phải query engine):

- ✅ Tăng tốc `SHOW TABLES` (~100ms vs ~1-2s)
- ✅ Compatibility với BI tools cũ
- ❌ KHÔNG dùng để query data
- ❌ KHÔNG bắt buộc (Delta tự discover tables)

**Query pattern:**

```sql
-- ✅ ĐÚNG - Query data
SELECT * FROM delta.gold.fact_transactions;

-- ✅ OK - List metadata
SHOW TABLES FROM hive.gold;

-- ❌ SAI - Query qua Hive
-- SELECT * FROM hive.gold.fact_transactions; -- Error!
```

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

### Q5: Làm sao biết hệ thống đang chạy tốt?

**A:** Check các indicators sau:

**1. Container health:**

```bash
docker ps --format "table {{.Names}}\t{{.Status}}"
# All containers: Up (healthy)
```

**2. Bronze streaming:**

```bash
docker logs bronze-streaming --tail 20
# ✅ "Batch X written successfully"
```

**3. Airflow DAGs:**

- http://localhost:8081
- `lakehouse_pipeline_taskflow`: Success (green)
- Recent runs: < 5 minutes ago

**4. Data count:**

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

# ✅ Normal:
# bronze-streaming: ~195% CPU (continuous)
# spark-master: ~50-100% CPU (when running jobs)
# airflow-*: ~10-30% CPU
```

### Q6: Khi nào nên restart services?

**A:** Chỉ restart khi:

1. **High CPU (>600% total)**: Spark jobs stuck
2. **Out of memory**: Container crash loop
3. **No data flow**: Bronze/Silver/Gold không cập nhật
4. **Config changes**: Thay đổi docker-compose.yml

**Restart commands:**

```bash
# Restart specific service
docker compose restart bronze-streaming

# Restart all Spark services
docker compose restart spark-master spark-worker bronze-streaming

# Full restart (keep data)
docker compose down
docker compose up -d

# Nuclear option (remove ALL data)
docker compose down -v
docker compose up -d --build
```

### Q7: Data producer chạy bao lâu?

**A:** Tùy mode:

**Streaming mode (default):**

- Chạy vô thời hạn (container restart: always)
- Insert ~5-10 transactions/second
- Fraud rate: 0.5-1%
- Dataset size: 1.8M records → ~2-4 tuần để hết

**Bulk load mode:**

```bash
docker exec data-producer python producer.py --bulk-load 50000
# → Chạy ~2-3 phút rồi exit
# Producer tự động tiếp tục streaming sau khi bulk load xong
```

### Q8: Làm sao backup data?

**A:** Backup 3 components:

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

Already in MinIO bucket (`s3a://lakehouse/models/`)

### Q9: Metabase không thấy tables?

**A:** Check connection config:

**Common mistakes:**

```yaml
# ❌ Wrong catalog
Catalog: hive # Should be "delta"

# ❌ Wrong port
Port: 8085 # Should be 8081 (internal) if Metabase in Docker

# ❌ Wrong host
Host: localhost # Should be "trino" if Metabase in Docker
```

**Correct config:**

```yaml
Database Type: Trino
Host: trino # Docker service name
Port: 8081 # Internal port
Catalog: delta # ⚠️ MUST use delta
Database: gold # Or silver/bronze
Username: (empty)
Password: (empty)
```

**Verify Trino working:**

```bash
docker exec trino trino --server localhost:8081 --execute "SHOW TABLES FROM delta.gold"
# ✅ Should list 5 tables
```

### Q10: Model training quá lâu?

**A:** Optimize resources:

**Before training:**

```powershell
# Free up ~2GB RAM + 1-2 CPU cores
.\scripts\prepare-ml-training.ps1
```

**Spark config (already optimized):**

```python
'--conf', 'spark.cores.max=2',
'--conf', 'spark.executor.cores=1',
'--conf', 'spark.executor.memory=1g',
'--conf', 'spark.driver.memory=1g',
```

**Expected time:**

- 50K records: ~2-3 minutes
- 1M records: ~10-15 minutes

**If still slow:**

- Reduce dataset: Filter recent data only
- Increase resources: Edit `.wslconfig` (Windows)
- Use sampling: Train on 10% data for testing

---

## 🔧 Common Operations

### Reset Everything (Clean Slate)

```bash
# ⚠️ WARNING: Deletes ALL data!
docker compose down -v
docker compose up -d --build

# Wait ~5 minutes for initialization
docker logs -f bronze-streaming
```

### Stop/Start Services (Keep Data)

```bash
# Stop (preserve volumes)
docker compose down

# Start
docker compose up -d

# Check status
docker compose ps
```

### View Logs

```bash
# Follow logs (Ctrl+C to exit)
docker logs -f bronze-streaming

# Last 50 lines
docker logs bronze-streaming --tail 50

# Filter by keyword
docker logs airflow-scheduler | grep "ERROR"

# Multiple services
docker logs bronze-streaming spark-master --tail 20
```

### Clean Up Disk Space

```bash
# Remove unused images
docker image prune -a

# Remove unused volumes
docker volume prune

# Remove build cache
docker builder prune
```

---

## 📚 Additional Resources

### Logs Location

- Container logs: `docker logs <service-name>`
- Airflow logs: Airflow UI → DAGs → Task → Logs
- Spark logs: http://localhost:8080 → Application → stdout/stderr

### Metrics & Monitoring

- Spark jobs: http://localhost:8080
- Airflow: http://localhost:8081
- MLflow: http://localhost:5000
- Trino: http://localhost:8085
- MinIO: http://localhost:9001

### Documentation Files

- `README.md` - Quick start guide
- `PROJECT_SPECIFICATION.md` - Technical specification
- `CHANGELOG.md` - This file (issues, FAQ)

---

**Document Version:** 1.0  
**Last Updated:** December 4, 2025  
**Maintained By:** Nhóm 6
