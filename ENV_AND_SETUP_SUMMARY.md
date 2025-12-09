# 📋 Environment Variables & Setup - Tổng kết

## 🔑 Quản lý Environment Variables

### ✅ GIẢI PHÁP: Dùng 1 file .env duy nhất ở root

```
real-time-fraud-detection-lakehouse/
├── .env                 # ✅ File duy nhất chứa tất cả env vars
├── .env.example         # Template để copy
└── services/
    └── fraud-chatbot/
        └── src/         # ❌ KHÔNG cần .env ở đây nữa
```

### Lý do:

1. **docker-compose.yml** đã config lấy từ `.env` root:

   ```yaml
   environment:
     - GOOGLE_API_KEY=${GOOGLE_API_KEY:-}
   ```

2. **Tránh duplicate config** → Dễ quản lý hơn

3. **Security:** Chỉ 1 file cần gitignore

---

## ✅ Kiểm tra API trong UI

### 1. Gemini API Status

**Vị trí:** Sidebar → System Status

**Hiển thị:**

```
✅ Gemini API: Connected (AIzaSyBzxr...)
[🧪 Test Gemini]  # Button để test thực tế
```

**Nếu chưa config:**

```
❌ Gemini API Key chưa config
💡 Set GOOGLE_API_KEY trong file .env
```

**Khi click "Test Gemini":**

- ✅ Success → "Gemini API hoạt động tốt!"
- ❌ Error → Hiển thị lỗi cụ thể (quota, invalid key...)

### 2. ML Model Status

**Hiển thị:**

```
✅ ML Model v1.0
[📊 Model Info]  # Button để xem chi tiết
```

**Khi click "Model Info":**

```json
{
  "model_type": "mlflow_model",
  "model_version": "1.0",
  "framework": "sklearn_RandomForest",
  "training_metrics": {
    "accuracy": 0.9845,
    "precision": 0.9123,
    "recall": 0.8756,
    "f1_score": 0.8935,
    "auc": 0.9567
  }
}
```

### 3. Database Status

**Button:** `🔌 Test Trino`

**Kết quả:**

- ✅ "Trino: 1,234,567 records"
- ❌ "Trino: Connection refused..."

---

## ✅ Migrations tự động

### Database init script đã bao gồm TẤT CẢ

File: `database/init_postgres.sql`

**Các bảng được tạo tự động:**

```sql
-- ✅ transactions
CREATE TABLE IF NOT EXISTS transactions (...);

-- ✅ fraud_predictions (with UNIQUE constraint)
CREATE TABLE IF NOT EXISTS fraud_predictions (
    trans_num VARCHAR(100) UNIQUE NOT NULL,
    ...
);

-- ✅ chat_history (with sql_query column)
CREATE TABLE IF NOT EXISTS chat_history (
    sql_query TEXT,
    ...
);

-- ✅ producer_checkpoint
CREATE TABLE IF NOT EXISTS producer_checkpoint (...);
```

### Khi nào chạy?

**Tự động khi:**

```bash
docker-compose up -d postgres
```

PostgreSQL container sẽ:

1. Kiểm tra database `frauddb` có chưa
2. Nếu chưa → Chạy `init_postgres.sql`
3. Tạo tất cả tables + indexes
4. Grant permissions

### Không cần chạy migrations thủ công!

**Trước đây (v1.0):**

```bash
# Phải chạy thủ công
.\scripts\run-migrations.ps1
```

**Bây giờ (v2.0):**

```bash
# Tự động rồi, chỉ cần:
docker-compose up -d
```

### Verify tables

```bash
docker exec -it postgres psql -U postgres -d frauddb -c "\dt"
```

**Expected output:**

```
              List of relations
 Schema |        Name         | Type  |  Owner
--------+---------------------+-------+----------
 public | chat_history        | table | postgres
 public | fraud_predictions   | table | postgres
 public | transactions        | table | postgres
 public | producer_checkpoint | table | postgres
```

---

## ✅ First-time setup workflow

### Người mới clone về:

1. **Copy .env:**

   ```bash
   cp .env.example .env
   ```

2. **Sửa API key:**

   ```bash
   notepad .env  # Windows
   nano .env     # Linux
   ```

   Thay `your_gemini_api_key_here` → API key thật

3. **Start services:**

   ```bash
   docker-compose up -d
   ```

4. **Verify trong UI:**
   - http://localhost:8501
   - Sidebar → System Status
   - Click "🧪 Test Gemini" → ✅
   - Click "📊 Model Info" → ✅
   - Click "🔌 Test Trino" → ✅

### Không cần:

- ❌ Chạy migrations thủ công
- ❌ Tạo database/tables thủ công
- ❌ Cấu hình .env trong từng service

---

## 🔧 Troubleshooting

### Issue 1: "Gemini API Key chưa config"

**Nguyên nhân:** File .env không tồn tại hoặc key rỗng

**Fix:**

```bash
# Check file exists
cat .env

# Check key
grep GOOGLE_API_KEY .env

# Expected:
GOOGLE_API_KEY=AIzaSy...  (không phải "your_gemini_api_key_here")
```

### Issue 2: "Gemini API lỗi: 429 Quota exceeded"

**Nguyên nhân:** Đã hết quota miễn phí (15 requests/phút, 1500 requests/ngày)

**Fix:**

1. Đợi 24h để quota reset
2. Hoặc dùng API key khác
3. Hoặc upgrade lên paid plan

### Issue 3: "Table chat_history doesn't exist"

**Nguyên nhân:** Database chưa init hoặc init script lỗi

**Fix:**

```bash
# Recreate database
docker-compose down postgres
docker volume rm real-time-fraud-detection-lakehouse_postgres_data
docker-compose up -d postgres

# Wait 30 seconds
Start-Sleep -Seconds 30

# Verify
docker exec -it postgres psql -U postgres -d frauddb -c "\dt"
```

### Issue 4: API key không load vào container

**Nguyên nhân:** .env file không ở đúng vị trí

**Fix:**

```bash
# .env phải ở root, cùng cấp docker-compose.yml
ls -la | grep .env  # Linux/Mac
dir | findstr .env  # Windows

# Nếu không có → tạo mới
cp .env.example .env
```

---

## 📊 Comparison: Before vs After

### Before (v1.0)

```
services/fraud-chatbot/
├── .env              # ❌ Duplicate config
├── .env.template     # ❌ Confusing
└── app/
    └── chatbot.py    # ❌ No API check in UI
```

**Setup:**

```bash
# Phải config 2 nơi
cp .env.template .env  # Root
cd services/fraud-chatbot
cp .env.template .env  # Chatbot

# Phải chạy migrations thủ công
.\scripts\run-migrations.ps1
```

### After (v2.0)

```
├── .env              # ✅ Single source of truth
├── .env.example      # ✅ Clear template
└── services/fraud-chatbot/
    └── src/
        └── main.py   # ✅ API check in UI
```

**Setup:**

```bash
# Chỉ 1 file
cp .env.example .env

# Tự động migrations
docker-compose up -d
```

---

## ✅ Summary

| Feature         | Before                        | After               |
| --------------- | ----------------------------- | ------------------- |
| **Env files**   | 2 files (.env root + chatbot) | 1 file (.env root)  |
| **API check**   | Chỉ trong logs                | ✅ UI + Test button |
| **Model info**  | Phải call API thủ công        | ✅ Button trong UI  |
| **Migrations**  | Chạy script thủ công          | ✅ Tự động khi init |
| **First setup** | 5 bước                        | 3 bước              |
| **Verify**      | Check logs                    | ✅ UI dashboard     |

---

**Kết luận:**

- ✅ Dùng 1 file .env duy nhất ở root
- ✅ UI có đầy đủ status checks + test buttons
- ✅ Migrations tự động, không cần chạy thủ công
- ✅ First-time setup đơn giản: copy .env → start → verify trong UI
