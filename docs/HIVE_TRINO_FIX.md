# Hive Metastore & Trino Quick Fix Guide

## ⚠️ CẬP NHẬT QUAN TRỌNG: Không cần register vào Hive Metastore!

### Tại sao?

1. **Delta Lake tự quản lý metadata**: Delta format có `_delta_log/` chứa schema + transaction history
2. **Trino's Delta connector**: Đọc trực tiếp từ Delta format qua catalog `delta`
3. **Hive connector hạn chế**: KHÔNG đọc được Delta format, chỉ list tables
4. **Kết luận**: Register vào Hive Metastore = VÔ NGHĨA với Delta Lake!

### Cách đúng:

- ✅ **Metabase/Chatbot**: Kết nối `jdbc:trino://localhost:8085/delta`
- ✅ **Queries**: Dùng `delta.bronze.*`, `delta.silver.*`, `delta.gold.*`
- ❌ **KHÔNG**: Dùng `hive.*` catalog (sẽ lỗi "Cannot query Delta Lake table")

### Hive Metastore vẫn cần cho gì?

- Chỉ nếu bạn có **non-Delta tables** (Parquet, ORC)
- Hoặc muốn **catalog discovery** cho tools cũ
- Với project này: **KHÔNG CẦN THIẾT**

---

## Vấn đề: Hive Metastore không khởi động sau khi restart (Legacy)

### Nguyên nhân

- Schema đã tồn tại trong PostgreSQL DB
- Default entrypoint cố gắng init lại schema → lỗi "relation BUCKETING_COLS already exists"

### Giải pháp đã implement

#### 1. Custom Entrypoint Script

File: `deployment/hive-metastore/entrypoint.sh`

**Chức năng:**

- Kiểm tra PostgreSQL connection
- Check nếu schema đã tồn tại (query table `BUCKETING_COLS`)
- Chỉ init schema nếu chưa có
- Start Hive Metastore service

#### 2. Persistent Volume

File: `docker-compose.yml`

```yaml
metastore-db:
  volumes:
    - metastore_db:/var/lib/postgresql/data # Re-enabled
  healthcheck:
    test: ["CMD-SHELL", "pg_isready -U hive"]
```

**Lợi ích:**

- Schema persist giữa các lần restart
- Không mất metadata khi container restart
- Health check đảm bảo DB ready trước khi Hive Metastore start

---

## Trino CLI - Đúng cách sử dụng

### ⚠️ Lỗi thường gặp

```bash
# SAI - Port 8080 không tồn tại
docker exec -it trino trino
# Error: Failed to connect to localhost:8080
```

### ✅ Cách đúng

```bash
# ĐÚNG - Chỉ định port 8081
docker exec -it trino trino --server localhost:8081
```

### Query Examples

**1. List catalogs:**

```bash
docker exec -it trino trino --server localhost:8081 --execute "SHOW CATALOGS"
# Output: delta, hive, system
```

**2. List schemas (databases):**

```bash
docker exec -it trino trino --server localhost:8081 --execute "SHOW SCHEMAS FROM hive"
# Output: default, bronze, silver, gold, information_schema
```

**3. List tables:**

```bash
docker exec -it trino trino --server localhost:8081 --execute "SHOW TABLES FROM delta.gold"
# Output: dim_customer, dim_merchant, dim_time, dim_location, fact_transactions
```

**4. Query data:**

```bash
# ⚠️ QUAN TRỌNG: Dùng DELTA catalog (không phải hive)
docker exec -it trino trino --server localhost:8081 --execute "SELECT COUNT(*) FROM delta.bronze.transactions"
```

**5. Interactive mode:**

```bash
docker exec -it trino trino --server localhost:8081

# Then run queries:
trino> SHOW CATALOGS;
trino> USE delta.gold;  -- Dùng DELTA catalog!
trino> SELECT * FROM fact_transactions LIMIT 10;
trino> quit;
```

---

## Troubleshooting

### Issue 1: Hive Metastore exit code 1

**Logs:**

```
Error: ERROR: relation "BUCKETING_COLS" already exists
Schema initialization failed!
```

**Fix:**

```bash
# Option 1: Xóa volume và rebuild (mất toàn bộ metadata)
docker compose down -v
docker compose up -d --build

# Option 2: Chỉ xóa metastore DB (giữ lại data lakehouse)
docker compose down metastore-db hive-metastore
docker volume rm real-time-fraud-detection-lakehouse_metastore_db
docker compose up -d metastore-db
sleep 5
docker compose up -d hive-metastore
```

### Issue 2: Trino không kết nối được Hive Metastore

**Logs:**

```
HIVE_METASTORE_ERROR: Failed connecting to Hive metastore: [hive-metastore:9083]
```

**Fix:**

```bash
# 1. Check Hive Metastore đang chạy
docker ps --filter "name=hive-metastore"

# 2. Check health status
docker inspect hive-metastore | grep -A5 Health

# 3. Check logs
docker logs hive-metastore --tail 50

# 4. Restart Trino sau khi Hive Metastore healthy
docker compose restart trino
```

### Issue 3: Trino catalogs rỗng

**Problem:**

```sql
SHOW SCHEMAS FROM hive;
-- Output: chỉ có default và information_schema
```

**Fix:**

```bash
# Trigger Airflow DAG để register tables vào Hive
# Airflow UI: http://localhost:8081
# → lakehouse_pipeline_taskflow → Trigger DAG

# Hoặc check Bronze/Silver/Gold có data chưa
docker exec -it trino trino --server localhost:8081 --execute "SELECT COUNT(*) FROM delta.default.\"s3a://lakehouse/bronze/transactions\""
```

---

## Container Dependencies

```
metastore-db (PostgreSQL)
    ↓ (depends_on + healthcheck)
hive-metastore
    ↓ (wait for port 9083)
trino
    ↓ (query via thrift://hive-metastore:9083)
Spark Jobs (register tables)
    ↓ (create schemas: bronze, silver, gold)
Hive Metastore Tables
    ↓ (query via Trino)
Metabase / DBeaver
```

**Startup Order:**

1. `metastore-db` (health: pg_isready)
2. `hive-metastore` (health: nc -z localhost 9083)
3. `trino` (connects to hive-metastore:9083)
4. Spark jobs register tables → schemas appear in Trino

---

## Verification Checklist

**✅ Hive Metastore:**

```bash
# 1. Container running
docker ps | grep hive-metastore
# Status: Up, health: healthy

# 2. Port accessible
nc -zv localhost 9083
# Connection successful

# 3. Logs show "Starting Hive Metastore Server"
docker logs hive-metastore | grep "Starting Hive Metastore Server"
```

**✅ Trino:**

```bash
# 1. Can list catalogs
docker exec -it trino trino --server localhost:8081 --execute "SHOW CATALOGS"
# Output: delta, hive, system

# 2. Can access Hive catalog
docker exec -it trino trino --server localhost:8081 --execute "SHOW SCHEMAS FROM hive"
# Output: default, bronze, silver, gold (after tables registered)
```

**✅ Integration:**

```bash
# Tables registered via Airflow DAG
docker exec -it trino trino --server localhost:8081 --execute "SHOW TABLES FROM hive.gold"
# Output: 5 tables (4 dims + 1 fact)

# Can query data
docker exec -it trino trino --server localhost:8081 --execute "SELECT COUNT(*) FROM hive.gold.fact_transactions"
# Output: record count
```

---

## Maintenance

### Reset Hive Metastore (clean slate)

```bash
docker compose down hive-metastore metastore-db
docker volume rm real-time-fraud-detection-lakehouse_metastore_db
docker compose up -d metastore-db
sleep 10
docker compose up -d hive-metastore
```

### Rebuild Hive Metastore image

```bash
docker compose build hive-metastore
docker compose up -d hive-metastore
```

### Check schema in PostgreSQL directly

```bash
docker exec -it metastore-db psql -U hive -d metastore -c "\dt"
# Should show ~50 Hive Metastore tables including BUCKETING_COLS
```
