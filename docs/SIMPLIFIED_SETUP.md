# Simplified Setup - No More Manual Migrations! 🎉

## 📝 Tóm tắt thay đổi

**Trước đây:**

```bash
# 3 bước phức tạp
docker compose up -d --build
.\scripts\run-migrations.ps1  # ← Phải chạy thủ công!
docker exec data-producer python producer.py --bulk-load 50000
```

**Bây giờ:**

```bash
# 2 bước đơn giản
docker compose up -d --build  # ← Database tự động init!
docker exec data-producer python producer.py --bulk-load 50000
```

## ✅ Những gì đã thay đổi

### 1. **Gộp migrations vào `init_postgres.sql`**

**File:** `database/init_postgres.sql`

Đã tích hợp tất cả migrations:

- ✅ UNIQUE constraint trên `fraud_predictions.trans_num`
- ✅ Foreign key: `fraud_predictions.trans_num` → `transactions.trans_num`
- ✅ Indexes: `idx_fraud_predictions_time`, `idx_fraud_predictions_model_version`
- ✅ Table comments cho documentation
- ✅ `chat_history.sql_query` column

**Lợi ích:**

- PostgreSQL container tự động chạy `init_postgres.sql` khi khởi động lần đầu
- Không cần script migration riêng
- Fresh clone = clean setup

### 2. **Xóa files không cần thiết**

Files đã xóa:

- ❌ `database/migrations/001_fix_fraud_predictions.sql`
- ❌ `database/migrations/002_add_sql_query_to_chat_history.sql`
- ❌ `database/migrations/003_fraud_predictions_for_realtime.sql`
- ❌ `scripts/run-migrations.ps1`
- ❌ `scripts/run-migrations.sh`

**Lý do:** Tất cả đã merged vào `init_postgres.sql`

### 3. **Update Documentation**

Files đã update:

- ✅ `README.md` - Xóa section 2.1 về migrations
- ✅ `docs/SETUP_CHECKLIST.md` - Đơn giản hóa từ 8 bước → 6 bước

## 🚀 Fresh Clone Setup

```bash
# Step 1: Clone repo
git clone https://github.com/bin-bard/real-time-fraud-detection-lakehouse.git
cd real-time-fraud-detection-lakehouse

# Step 2: (Optional) Configure Gemini API for Chatbot
cp .env.example .env
nano .env  # Add GOOGLE_API_KEY

# Step 3: Start everything
docker compose up -d --build

# Step 4: Wait 5-10 minutes, then load data
docker exec data-producer python producer.py --bulk-load 50000

# Step 5: (Optional) Wait for Spark ETL pipeline or trigger manually
# Step 6: (Optional) Train ML model or wait for scheduled run

# DONE! 🎉
```

## 🔍 Verify Schema

Sau khi container postgres khởi động, verify schema:

```bash
docker exec postgres psql -U postgres -d frauddb -c "\d fraud_predictions"
```

**Expected output:**

```sql
Table "public.fraud_predictions"
Column              | Type                        | Default
--------------------+-----------------------------+--------------------------------
id                  | integer                     | nextval(...)
trans_num           | character varying(100)      |
prediction_score    | numeric(5,4)                |
is_fraud_predicted  | smallint                    |
model_version       | character varying(50)       |
prediction_time     | timestamp without time zone | now()

Indexes:
    "fraud_predictions_pkey" PRIMARY KEY, btree (id)
    "fraud_predictions_trans_num_key" UNIQUE CONSTRAINT, btree (trans_num)
    "idx_fraud_predictions_time" btree (prediction_time DESC)
    "idx_fraud_predictions_model_version" btree (model_version)

Foreign-key constraints:
    "fraud_predictions_trans_num_fkey" FOREIGN KEY (trans_num)
        REFERENCES transactions(trans_num)
```

✅ **All constraints và indexes tự động tạo!**

## 💡 Architecture Decision

**Why keep Foreign Key constraint?**

Thiết kế này chuẩn bị cho **real-time Kafka integration**:

```
Kafka CDC → Bronze Streaming → transactions table (INSERT)
                                      ↓
                                FastAPI Prediction
                                      ↓
                           fraud_predictions (INSERT)
```

**Flow:**

1. Kafka CDC capture transaction từ upstream system
2. Bronze streaming job insert vào `transactions` table
3. FastAPI auto-predict và insert vào `fraud_predictions`
4. Foreign key ensures data integrity

**Current behavior (Chatbot):**

- Chatbot predictions có `trans_num` prefix `CHAT_*` hoặc `MANUAL_*`
- FastAPI **skips DB save** cho những predictions này (check code)
- Vì vậy không conflict với foreign key

**Code reference:**

```python
# services/fraud-detection-api/app/main.py
def save_prediction_to_db(...):
    if trans_num.startswith(('CHAT_', 'MANUAL_')):
        logger.info(f"Skipping DB save for manual/chatbot prediction: {trans_num}")
        return True  # Skip save
    # ... normal DB save for real transactions
```

## 📊 Migration History (For Reference)

### Migration 001: Fix fraud_predictions

- Added UNIQUE constraint to `trans_num`
- Created index `idx_fraud_predictions_time`

### Migration 002: Chat history SQL query

- Added `sql_query TEXT` column to `chat_history`
- Created session index

### Migration 003: Real-time preparation

- Added foreign key constraint
- Added table comment
- Created model_version index

**All merged into `init_postgres.sql`** ✅

## 🎯 Benefits

1. **Simpler Setup** - Clone và chạy, không cần migration manual
2. **Idempotent** - `CREATE TABLE IF NOT EXISTS` ensures safety
3. **Self-Documented** - Schema có comments trong SQL
4. **Production-Ready** - Foreign key sẵn sàng cho Kafka integration
5. **Clean Architecture** - Mọi thứ trong 1 file init dễ review

## 🔧 Troubleshooting

### Q: Schema không đúng sau khi `docker compose up`?

```bash
# Option 1: Rebuild postgres container
docker compose down postgres
docker volume rm real-time-fraud-detection-lakehouse_postgres_data
docker compose up -d postgres

# Option 2: Check init script logs
docker logs postgres | grep -i "init"
```

### Q: Foreign key conflict khi chatbot predict?

**Không xảy ra** - API skip save cho `CHAT_*` và `MANUAL_*` transactions.

Verify:

```bash
docker logs fraud-detection-api --tail 50 | grep "Skipping"
```

Expected:

```
Skipping DB save for manual/chatbot prediction: CHAT_abc123
```

### Q: Muốn reset database?

```bash
docker compose down -v  # Xóa tất cả volumes
docker compose up -d     # Init lại từ đầu
```

## 📚 Related Docs

- [README.md](../README.md) - Main setup guide
- [SETUP_CHECKLIST.md](SETUP_CHECKLIST.md) - Step-by-step verification
- [REALTIME_ARCHITECTURE.md](REALTIME_ARCHITECTURE.md) - Kafka integration design

---

**Last Updated:** 2025-12-10  
**Status:** ✅ Production Ready
