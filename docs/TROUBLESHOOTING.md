# Troubleshooting Guide - Hive Metastore & Trino Integration

> **Tài liệu này ghi lại các vấn đề gặp phải và giải pháp khi setup Trino + Hive Metastore cho Data Lakehouse**

---

## 📋 Tổng Quan

### Mục Tiêu

Setup Trino để Metabase có thể query Delta Lake tables. **Hive Metastore là metadata cache (optional)**.

### ⚠️ LƯU Ý QUAN TRỌNG

- **Hive Metastore**: CHỈ là metadata cache (giúp `SHOW TABLES` nhanh)
- **Delta catalog**: PHẢI dùng để query data (`delta.bronze.*`, `delta.silver.*`, `delta.gold.*`)
- **Hive catalog**: CHỈ list tables, KHÔNG query được Delta format

### Kiến Trúc Cuối Cùng

```
Metabase (Visualization)
    ↓ SQL Queries (jdbc:trino://trino:8081/delta)
Trino (Query Engine - port 8081)
    ├─→ Delta Catalog (Query data: đọc _delta_log/ + S3)
    └─→ Hive Catalog (List metadata: SHOW TABLES nhanh)
            ↓
Hive Metastore (Metadata Cache - port 9083) ← OPTIONAL!
    ↓ PostgreSQL
metastore-db (Schema info)

MinIO (Object Storage - port 9000)
    └── Delta Lake Files (_delta_log/ + Parquet)
        ├── bronze/
        ├── silver/
        └── gold/
```

---

## ⚠️ Vấn Đề #1: Hive Metastore Schema Conflicts

### Triệu Chứng

```
ERROR: relation "BUCKETING_COLS" already exists
FATAL: database system is corrupted
```

Mỗi lần restart container, Hive Metastore crash do conflict schema trong PostgreSQL.

### Nguyên Nhân

- **Volume persistence**: PostgreSQL data được persist qua `metastore_db` volume
- Khi Hive Metastore restart → cố init schema lại → schema đã tồn tại → crash
- `initSchema=true` + existing schema = conflict

### Giải Pháp ✅

**Xóa volume persistence** trong `docker-compose.yml`:

```yaml
# ❌ CŨ (gây lỗi):
metastore-db:
  image: postgres:14
  volumes:
    - metastore_db:/var/lib/postgresql/data # ← XÓA DÒNG NÀY

volumes:
  metastore_db: # ← XÓA VOLUME DEFINITION
```

```yaml
# ✅ MỚI (hoạt động):
metastore-db:
  image: postgres:14
  # Không có volumes - fresh DB mỗi lần start
  environment:
    POSTGRES_DB: metastore
    POSTGRES_USER: hive
    POSTGRES_PASSWORD: hive123
```

**Kết Quả:**

- Fresh PostgreSQL DB mỗi lần restart
- Hive Metastore auto-init schema thành công
- Không còn conflict errors
- Tables được re-register tự động qua `hive-registration` service

---

## ⚠️ Vấn Đề #2: Hadoop Version Mismatch

### Triệu Chứng

```
java.lang.ClassNotFoundException: org.apache.hadoop.fs.s3a.S3AFileSystem
java.lang.NoSuchMethodError: org.apache.hadoop.fs.statistics.IOStatisticsSource.getIOStatistics()
```

### Nguyên Nhân

- **Hive 3.1.3** sử dụng **Hadoop 3.1.0** internally
- Custom JARs dùng **Hadoop 3.3.4** → version conflict
- Methods không tương thích giữa Hadoop 3.1.0 vs 3.3.4

### Giải Pháp ✅

**Downgrade về Hadoop 3.1.0 compatible JARs:**

```bash
# deployment/hive-metastore/lib/
hadoop-aws-3.1.0.jar              # ← Từ 3.3.4 → 3.1.0
aws-java-sdk-bundle-1.11.375.jar  # ← Từ 1.12.262 → 1.11.375

# XÓA các JARs gây conflict:
# hadoop-common-3.3.4.jar         # ← XÓA
# hadoop-shaded-guava-*.jar       # ← XÓA
```

**Dockerfile update:**

```dockerfile
FROM apache/hive:3.1.3

# Copy JARs vào CẢ 2 locations để chắc chắn
COPY lib/*.jar /opt/hive/lib/
COPY lib/*.jar /opt/hadoop/share/hadoop/common/lib/

# Copy S3A configuration
COPY core-site.xml /opt/hadoop/etc/hadoop/core-site.xml
```

**Kết Quả:**

- Không còn ClassNotFoundException
- S3AFileSystem load thành công
- Compatible với Hive 3.1.3

---

## ⚠️ Vấn Đề #3: MinIO Credential Mismatch

### Triệu Chứng

```
Status Code: 403, AWS Service: Amazon S3, AWS Request ID: null
AWS Error Code: null, AWS Error Message: Forbidden
```

### Nguyên Nhân

- MinIO service dùng credentials: `minio` / `minio123`
- Hive Metastore config dùng credentials: `minioadmin` / `minioadmin`
- → 403 Forbidden khi access S3

### Giải Pháp ✅

**Update `core-site.xml`:**

```xml
<!-- deployment/hive-metastore/core-site.xml -->
<configuration>
  <property>
    <name>fs.s3a.impl</name>
    <value>org.apache.hadoop.fs.s3a.S3AFileSystem</value>
  </property>

  <property>
    <name>fs.s3a.access.key</name>
    <value>minio</value>  <!-- ← Từ minioadmin → minio -->
  </property>

  <property>
    <name>fs.s3a.secret.key</name>
    <value>minio123</value>  <!-- ← Từ minioadmin → minio123 -->
  </property>

  <property>
    <name>fs.s3a.endpoint</name>
    <value>http://minio:9000</value>
  </property>

  <property>
    <name>fs.s3a.path.style.access</name>
    <value>true</value>
  </property>

  <property>
    <name>fs.s3a.connection.ssl.enabled</name>
    <value>false</value>
  </property>
</configuration>
```

**Kết Quả:**

- Hive Metastore connect MinIO thành công
- `CREATE SCHEMA` và `CREATE TABLE` hoạt động
- Trino query Delta Lake qua Hive Metastore

---

## ⚠️ Vấn Đề #4: MSCK REPAIR TABLE Incompatible

### Triệu Chứng

```
ERROR: Failed to register bronze.transactions: MSCK REPAIR TABLE is not supported for v2 tables
ERROR: Failed to register gold.dim_customer: MSCK REPAIR TABLE is not supported for v2 tables
```

Chỉ 2/7 tables được register thành công (dim_location, fact_transactions).

### Nguyên Nhân

- **Delta Lake v2** sử dụng format mới với transaction log (`_delta_log/`)
- `MSCK REPAIR TABLE` là Hive command cho format cũ (Parquet partitioned)
- Delta Lake tự động quản lý partitions → không cần MSCK

### Giải Pháp ✅

**Xóa MSCK REPAIR command** trong `register_tables_to_hive.py`:

```python
# ❌ CŨ (line 63):
spark.sql(f"MSCK REPAIR TABLE {database}.{table_name}")

# ✅ MỚI (line 63-64):
# Note: MSCK REPAIR TABLE not supported for Delta v2 tables
# Delta automatically manages partitions
```

**Lý Do:**

- Delta Lake tự động update partition metadata trong `_delta_log/`
- Trino đọc metadata trực tiếp từ Delta transaction log
- CREATE EXTERNAL TABLE đã đủ để register

**Kết Quả:**

- ✅ 7/7 tables registered thành công
- ✅ Bronze: transactions (25K records)
- ✅ Silver: transactions (25K records)
- ✅ Gold: dim_customer, dim_merchant, dim_time, dim_location, fact_transactions

---

## ⚠️ Vấn Đề #5: Hive Metastore Connection Refused

### Triệu Chứng

```
org.apache.thrift.transport.TTransportException: java.net.ConnectException: Connection refused
WARN metastore: Failed to connect to the MetaStore Server...
```

### Nguyên Nhân

- Spark job start quá nhanh trước khi Hive Metastore ready
- Thrift server chưa listen trên port 9083

### Giải Pháp ✅

**Thêm retry logic và wait** trong registration service:

```python
# spark/app/register_tables_to_hive.py
import time

def wait_for_hive_metastore(max_retries=20, retry_interval=5):
    """Wait for Hive Metastore to be ready"""
    for attempt in range(max_retries):
        try:
            spark = create_spark_session()
            # Test connection
            spark.sql("SHOW DATABASES").collect()
            logger.info("✅ Hive Metastore is ready!")
            return spark
        except Exception as e:
            if attempt < max_retries - 1:
                logger.warning(f"Attempt {attempt+1}/{max_retries} - Hive Metastore not ready, retrying...")
                time.sleep(retry_interval)
            else:
                raise
```

**Docker depends_on:**

```yaml
# docker-compose.yml
hive-registration:
  depends_on:
    - hive-metastore
    - spark-master
  # Wait for Hive Metastore to initialize
```

**Kết Quả:**

- Registration job đợi Metastore ready
- Không còn connection refused errors
- Auto-retry thành công sau 10-15 giây

---

## ⚠️ Vấn Đề #6: Trino Port Confusion

### Triệu Chứng

```
java.net.ConnectException: Failed to connect to localhost/[0:0:0:0:0:0:0:1]:8080
```

Metabase không connect được Trino.

### Nguyên Nhân

- Trino internal port: **8081** (HTTP coordinator)
- Trino external port: **8085** (mapped to host)
- Default `trino` CLI tool dùng port 8080 → sai

### Giải Pháp ✅

**Sử dụng đúng port:**

```bash
# ✅ Inside Docker network:
docker exec trino trino --server localhost:8081 --execute "SHOW TABLES FROM delta.gold"

# ✅ From host machine:
trino --server localhost:8085 --execute "SHOW TABLES FROM delta.gold"
```

**Metabase configuration:**

```yaml
Database Type: Trino
Host: trino # ← Docker service name
Port: 8081 # ← Internal port
Catalog: delta
Database: gold
```

**Nếu Metabase chạy ngoài Docker:**

```yaml
Host: localhost
Port: 8085 # ← External mapped port
```

**Kết Quả:**

- Metabase connect Trino thành công
- Query all 7 tables từ bronze/silver/gold
- Dashboards hoạt động bình thường

---

## 📊 Verification Checklist

### 1. Hive Metastore Health

```bash
docker logs hive-metastore --tail 30

# ✅ Mong đợi:
# Starting Hive Metastore Server
# Metastore connection URL: jdbc:postgresql://metastore-db:5432/metastore
# Starting hive metastore on port 9083
```

### 2. Hive Registration Status

```bash
docker logs hive-registration --tail 50

# ✅ Mong đợi:
# ✅ Registered bronze.transactions (25,000 records)
# ✅ Registered silver.transactions (25,000 records)
# ✅ Registered gold.dim_customer
# ✅ Registered gold.dim_merchant
# ✅ Registered gold.dim_time
# ✅ Registered gold.dim_location
# ✅ Registered gold.fact_transactions (25,000 records)
# ✅ Registration completed successfully!
```

### 3. Trino Connectivity

```bash
# Test Trino CLI
docker exec trino trino --server localhost:8081 --execute "SHOW CATALOGS"

# ✅ Mong đợi:
# "delta"
# "hive"
# "system"

# Test schemas
docker exec trino trino --server localhost:8081 --execute "SHOW SCHEMAS FROM delta"

# ✅ Mong đợi:
# "bronze"
# "silver"
# "gold"
# "information_schema"

# Test tables
docker exec trino trino --server localhost:8081 --execute "SHOW TABLES FROM delta.gold"

# ✅ Mong đợi:
# "dim_customer"
# "dim_location"
# "dim_merchant"
# "dim_time"
# "fact_transactions"
```

### 4. Query Sample Data

```bash
docker exec trino trino --server localhost:8081 --execute "
SELECT
    'bronze.transactions' as table_name,
    COUNT(*) as records
FROM delta.bronze.transactions
UNION ALL
SELECT
    'silver.transactions',
    COUNT(*)
FROM delta.silver.transactions
UNION ALL
SELECT
    'gold.fact_transactions',
    COUNT(*)
FROM delta.gold.fact_transactions
"

# ✅ Mong đợi:
# "bronze.transactions","25000"
# "silver.transactions","25000"
# "gold.fact_transactions","25000"
```

---

## 🔧 Final Working Configuration

### Hive Metastore

- **Image**: Custom from `apache/hive:3.1.3`
- **JARs**: Hadoop 3.1.0 + AWS SDK 1.11.375
- **Database**: PostgreSQL (no persistence)
- **Port**: 9083 (Thrift)
- **Config**: `core-site.xml` with S3A settings

### Trino

- **Image**: `trinodb/trino:latest`
- **Catalogs**:
  - `delta` (Delta Lake via Hive Metastore)
  - `hive` (backup option)
- **Ports**:
  - Internal: 8081
  - External: 8085

### Registration Service

- **Script**: `spark/app/register_tables_to_hive.py`
- **Schedule**: Every 1 hour
- **Tables**: 7 tables (1 bronze + 1 silver + 5 gold)
- **Mode**: PySpark with Hive support

### MinIO

- **Credentials**: `minio` / `minio123`
- **Endpoint**: `http://minio:9000`
- **Bucket**: `lakehouse`
- **Structure**: `/bronze/`, `/silver/`, `/gold/`

---

## 🎯 Key Learnings

### 1. Volume Persistence

❌ **Không nên** persist Metastore DB khi dùng `initSchema=true`  
✅ **Nên** để fresh DB + auto re-register tables

### 2. Version Compatibility

❌ Hive 3.1.3 + Hadoop 3.3.4 = NoSuchMethodError  
✅ Hive 3.1.3 + Hadoop 3.1.0 = Compatible

### 3. Delta Lake Format

❌ MSCK REPAIR TABLE cho Delta v2 = Not supported  
✅ CREATE EXTERNAL TABLE USING DELTA = Đủ rồi

### 4. Credential Consistency

❌ MinIO credentials khác core-site.xml = 403 Forbidden  
✅ Credentials match everywhere = Success

### 5. Port Configuration

❌ Trino default port 8080 = Connection refused  
✅ Trino actual port 8081 (internal) / 8085 (external) = Working

---

## ⚠️ Vấn Đề #7: ML Training với ít samples (~15-20)

### Triệu Chứng

MLflow UI hiển thị:

- `train_samples: 14-17`
- `test_samples: 3-4`
- Tổng chỉ ~20 samples

User có 4000+ records trong Silver layer nhưng ML chỉ train với ~20 samples.

### Nguyên Nhân

**ĐÂY KHÔNG PHẢI LỖI - Đây là real-world fraud detection behavior!**

| Metric                    | Value           | Explanation                       |
| ------------------------- | --------------- | --------------------------------- |
| Total records (Silver)    | ~4,200          | Sau vài phút streaming            |
| **Fraud transactions**    | ~10 (0.24%)     | **Real-world fraud rate: 0.5-1%** |
| Non-fraud transactions    | ~4,190 (99.76%) | Majority class                    |
| **After class balancing** |                 |                                   |
| Fraud (keep all)          | 10              | Minority class - giữ nguyên       |
| Non-fraud (undersampled)  | 10              | Undersampling để balance 1:1      |
| **Total balanced**        | 20              | Training dataset                  |
| Train set (80%)           | ~16             |                                   |
| Test set (20%)            | ~4              |                                   |

**Lý do:**

1. ✅ **Fraud imbalance**: Real-world fraud rate rất thấp (0.5-1%)
2. ✅ **Class balancing**: ML job undersample majority class để tránh bias
3. ✅ **Early stage**: Data producer mới chạy vài phút → ít fraud samples
4. ⏰ **Cần thời gian**: Đợi 2-4 giờ để có ~50-100 fraud samples → training tốt hơn

### Giải Pháp ✅

**Option 1: Bulk Load Initial Data (Recommended)**

```powershell
# Load 50K transactions ngay lập tức (~250 fraud samples)
docker exec data-producer python producer.py --bulk-load 50000

# Kết quả:
# - ~50K records loaded trong 2-3 phút
# - ~250 fraud transactions (0.5% fraud rate)
# - Đủ data cho ML training ngay
# - Sau đó tiếp tục streaming bình thường
```

**Cơ chế hoạt động:**

1. ✅ Bulk load → Insert nhanh 50K records vào PostgreSQL
2. ✅ Debezium CDC → Capture INSERT events → Kafka
3. ✅ Bronze streaming → Xử lý CDC events → Delta Lake
4. ✅ Silver/Gold batch → Chạy 5 phút sau → Ready for training
5. ✅ Data producer → Tiếp tục streaming với records còn lại

**Checkpoint safe:**

- ✅ PostgreSQL SERIAL primary key → Không duplicate
- ✅ Debezium LSN (Log Sequence Number) → Resume từ đúng vị trí
- ✅ Spark streaming checkpoint → Exactly-once semantics

**Option 2: Tăng tốc streaming**

```python
# Modify services/data-producer/producer.py
# Line ~35: Giảm sleep time
time.sleep(0.5)  # Thay vì time.sleep(5)

# Restart
docker compose restart data-producer
```

**Option 3: Đợi tự nhiên**

- Chờ 2-4 giờ để data producer insert đủ data
- Fraud rate 0.5% → 100 frauds cần ~20K transactions
- Schedule: Daily 2 AM training (tự động qua Airflow)

### Khi nào nên re-train?

- ✅ Sau khi có **≥100 fraud samples** (better accuracy)
- ✅ Schedule: Daily 2 AM (tự động qua Airflow)
- ✅ Manual trigger: Airflow UI → model_retraining_taskflow → ▶️

### Verify data distribution

```sql
-- Check fraud distribution
docker exec trino trino --server localhost:8081 --execute \
  "SELECT is_fraud, COUNT(*) as count FROM delta.silver.transactions GROUP BY is_fraud"

-- Expected output (early stage):
-- "0","4190"   -- Non-fraud
-- "1","10"     -- Fraud (0.24%)

-- Expected output (after bulk load 50K):
-- "0","49750"  -- Non-fraud
-- "1","250"    -- Fraud (0.5%)
```

---

## 📖 Related Documentation

- **Metabase Setup**: [`docs/METABASE_SETUP.md`](./METABASE_SETUP.md) - Connection settings & sample queries
- **Project Spec**: [`docs/PROJECT_SPECIFICATION.md`](./PROJECT_SPECIFICATION.md) - Full architecture details
- **Hive Metastore Role**: [`docs/HIVE_METASTORE_ROLE.md`](./HIVE_METASTORE_ROLE.md) - Metadata cache vs query engine

---

## 💡 Quick Fixes

### Reset Everything

```bash
# Stop all services
docker-compose down

# Remove volumes (optional - only if needed)
docker volume prune -f

# Restart fresh
docker-compose up -d

# Wait 2-3 minutes for registration
docker logs -f hive-registration
```

### Force Re-registration

```bash
# Restart registration service
docker-compose restart hive-registration

# Watch logs
docker logs -f hive-registration
```

### Check Service Health

```bash
# All services status
docker-compose ps

# CPU/Memory usage
docker stats --no-stream

# Specific service logs
docker logs <service-name> --tail 50
```

---

## ✅ Success Indicators

Khi mọi thứ hoạt động đúng, bạn sẽ thấy:

1. ✅ Hive Metastore running without errors
2. ✅ Hive registration completes with 7/7 tables
3. ✅ Trino SHOW CATALOGS returns `delta` and `hive`
4. ✅ Trino SHOW SCHEMAS returns `bronze`, `silver`, `gold`
5. ✅ Trino SHOW TABLES returns all 7 tables
6. ✅ Trino SELECT queries return data
7. ✅ Metabase connects and shows all tables
8. ✅ No 403 Forbidden errors in logs
9. ✅ No ClassNotFoundException errors
10. ✅ No MSCK REPAIR errors

**Total time from start to fully operational: ~5 minutes**

---

**Last Updated**: December 2, 2025  
**Status**: ✅ All issues resolved, system operational
