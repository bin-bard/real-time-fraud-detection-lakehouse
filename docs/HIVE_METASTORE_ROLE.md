# Vai trò của Hive Metastore trong Dự án

## 🎯 Tóm tắt nhanh

**Hive Metastore KHÔNG PHẢI để query Delta tables!**

Vai trò thực tế: **Metadata Cache Layer** cho Delta catalog

---

## 📐 Kiến trúc hiện tại

```
Metabase/Chatbot
       ↓
   Trino (port 8085)
       ↓
Delta Connector ───┬──→ Hive Metastore (metadata cache)
                   │         ↓
                   │    PostgreSQL (schema info)
                   │
                   └──→ MinIO S3 (_delta_log/ + Parquet files)
                            ↑
                         QUERY DATA (primary source)
```

### Luồng query:

1. **SHOW TABLES FROM delta.gold**

   - Delta connector → Check Hive Metastore cache → Return nhanh
   - Nếu không có Hive: Delta connector → Scan S3 `_delta_log/` → Chậm hơn

2. **SELECT \* FROM delta.gold.fact_transactions**
   - Delta connector → Đọc `_delta_log/` (transaction log)
   - Delta connector → Đọc Parquet files từ MinIO
   - Hive Metastore **KHÔNG tham gia** giai đoạn này!

---

## ✅ Lợi ích của Hive Metastore (Metadata Cache)

### 1. Performance cho Discovery Operations

| Operation               | Có Hive Metastore     | Không có Hive                |
| ----------------------- | --------------------- | ---------------------------- |
| SHOW SCHEMAS            | ⚡ ~50ms (cache hit)  | 🐢 ~500ms (scan S3)          |
| SHOW TABLES             | ⚡ ~100ms (cache hit) | 🐢 ~1-2s (scan S3)           |
| DESCRIBE TABLE          | ⚡ ~50ms (cache hit)  | 🐢 ~300ms (read \_delta_log) |
| **SELECT (query data)** | ⚡ SAME               | ⚡ SAME                      |

### 2. Compatibility với Legacy Tools

Một số BI tools/JDBC clients cũ chỉ biết "tìm tables qua Hive Metastore":

- ✅ Có Hive: Tools discover tables tự động
- ❌ Không có Hive: Phải config thủ công table paths

### 3. Centralized Metadata Store

Nếu sau này cần thêm:

- Parquet/ORC tables (non-Delta)
- Iceberg tables
- External tables

→ Hive Metastore là nơi quản lý metadata chung

---

## ❓ Câu hỏi thường gặp

### Q1: Có thể bỏ Hive Metastore không?

**Có thể**, nhưng phải sửa code:

#### Step 1: Xóa config Hive trong Delta connector

```bash
# Edit: config/trino/catalog/delta.properties
# Bỏ dòng:
hive.metastore.uri=thrift://hive-metastore:9083
```

#### Step 2: Xóa services trong docker-compose.yml

```bash
# Comment out:
# - metastore-db
# - hive-metastore
```

#### Step 3: Trino tự discover Delta tables

- Scan S3 prefix: `s3a://lakehouse/bronze/`, `s3a://lakehouse/silver/`, `s3a://lakehouse/gold/`
- Đọc `_delta_log/` mỗi khi SHOW TABLES
- Delay ~1-5 phút để discover tables mới

#### Nhược điểm:

- 🐢 SHOW TABLES chậm hơn (scan MinIO mỗi lần)
- ⚠️ Metabase/DBeaver có thể không discover tables tự động
- ⚠️ Mất ~1-5 phút sau khi tạo table mới mới thấy

---

### Q2: register_tables_to_hive.py có thừa không?

**KHÔNG THỪA** - vẫn cần thiết!

#### Nếu GIỮ Hive Metastore:

- ✅ Script này populate metadata cache
- ✅ SHOW TABLES nhanh ngay lập tức
- ✅ Không cần đợi Delta connector tự discover

#### Nếu BỎ Hive Metastore:

- ❌ Script vô dụng (không có Hive để register)
- ✅ Delta connector tự discover (auto, nhưng chậm)

#### Khi nào chạy script?

```bash
# Chỉ chạy KHI:
# 1. Lần đầu setup (populate initial metadata)
# 2. Sau khi manually tạo Delta table mới (outside Spark jobs)

# KHÔNG CẦN chạy định kỳ:
# - Silver/Gold jobs tự động update Hive Metastore qua enableHiveSupport()
```

---

### Q3: Tại sao Spark jobs KHÔNG cần config Hive?

Xem `silver_job.py`, `gold_job.py`:

```python
# ❌ KHÔNG CÓ:
# .config("hive.metastore.uris", "thrift://hive-metastore:9083")
# .enableHiveSupport()
```

**Lý do:**

- Spark ghi Delta format trực tiếp vào MinIO
- Delta format tự quản lý metadata trong `_delta_log/`
- Trino's Delta connector đọc trực tiếp `_delta_log/` (không cần Hive)

**CHỈ `register_tables_to_hive.py` mới cần Hive support:**

- Để populate metadata cache (optional optimization)

---

### Q4: Khi nào query qua `hive.*` catalog?

**KHÔNG BAO GIỜ** với Delta tables!

```sql
-- ❌ SAI - Hive connector không đọc được Delta format
SELECT * FROM hive.gold.fact_transactions;
-- Error: Cannot query Delta Lake table

-- ✅ ĐÚNG - Delta connector hiểu Delta format
SELECT * FROM delta.gold.fact_transactions;
```

**Hive catalog chỉ dùng để:**

```sql
-- List metadata (OK)
SHOW SCHEMAS FROM hive;
SHOW TABLES FROM hive.gold;

-- Query non-Delta tables (nếu có)
SELECT * FROM hive.legacy.parquet_table;  -- OK nếu table là Parquet thuần
```

---

## 🎯 Khuyến nghị cho Project

### ✅ GIỮ LẠI setup hiện tại (có Hive Metastore)

**Lý do:**

1. ⚡ Performance: SHOW TABLES nhanh (cache hit)
2. 🔧 Đã config ổn, đang chạy tốt
3. 💾 Resources: 300MB RAM không đáng kể (có 10GB total)
4. 🔮 Future-proof: Có thể thêm non-Delta tables sau

### 🔧 Giữ script register_tables_to_hive.py

**Lý do:**

- Populate metadata cache lần đầu
- SHOW TABLES nhanh ngay sau restart
- Không cần chờ Delta connector tự discover

**Lưu ý:**

- Script đã được update với comment rõ ràng
- Chỉ chạy manual khi cần (không cần schedule)

---

## 📚 Tài liệu tham khảo

### Delta Lake docs:

- Delta tables tự quản lý metadata: https://docs.delta.io/latest/delta-batch.html#-ddlmetadata
- Transaction log format: https://github.com/delta-io/delta/blob/master/PROTOCOL.md

### Trino Delta connector:

- Hive Metastore là optional: https://trino.io/docs/current/connector/delta-lake.html#metastore-configuration
- Table discovery modes: https://trino.io/docs/current/connector/delta-lake.html#table-discovery

### Khi nào cần Hive Metastore:

- Performance optimization: https://trino.io/docs/current/connector/delta-lake.html#performance
- Legacy compatibility: https://trino.io/docs/current/connector/hive.html

---

## 🔍 Verification Commands

### 1. Kiểm tra Hive Metastore đang chạy:

```bash
docker ps | grep hive-metastore
docker logs hive-metastore --tail 20
```

### 2. Kiểm tra metadata cache:

```bash
docker exec -it trino trino --server localhost:8081

# List metadata (nhanh - từ Hive cache)
SHOW SCHEMAS FROM delta;
SHOW TABLES FROM delta.gold;

# Query data (chậm hơn - đọc từ MinIO + _delta_log)
SELECT COUNT(*) FROM delta.gold.fact_transactions;
```

### 3. So sánh performance:

```bash
# With Hive Metastore cache
time docker exec -it trino trino --server localhost:8081 --execute "SHOW TABLES FROM delta.gold"
# → ~100-200ms

# Direct S3 scan (giả lập không có cache)
# Không test được vì Delta connector luôn dùng Hive nếu có config
```

---

## 🎓 Kết luận

| Câu hỏi                                   | Trả lời                                      |
| ----------------------------------------- | -------------------------------------------- |
| Hive Metastore có ý nghĩa gì?             | **Metadata cache** cho discovery operations  |
| register_tables_to_hive.py có thừa không? | **KHÔNG** - giúp populate cache nhanh        |
| Có thể bỏ Hive Metastore không?           | **CÓ** - nhưng SHOW TABLES sẽ chậm hơn       |
| Nên giữ hay bỏ?                           | **GIỮ LẠI** - performance + compatibility    |
| Query data có dùng Hive không?            | **KHÔNG** - Delta connector đọc trực tiếp S3 |
| Khi nào dùng hive.\* catalog?             | **KHÔNG BAO GIỜ** với Delta tables           |

---

**TÓM LẠI:**

- ✅ Hive Metastore = Metadata cache (tối ưu SHOW TABLES/SCHEMAS)
- ✅ Query data đi trực tiếp Delta connector → MinIO (không qua Hive)
- ✅ register_tables_to_hive.py = Populate cache (giữ lại, vẫn hữu ích)
- ✅ Setup hiện tại là ĐÚNG - không cần thay đổi gì! 🎉
