# 🚀 Setup Guide - First Time Installation

## Yêu cầu

- Docker Desktop
- Git
- PowerShell (Windows) hoặc Bash (Linux/Mac)

## Bước 1: Clone repository

```bash
git clone https://github.com/bin-bard/real-time-fraud-detection-lakehouse.git
cd real-time-fraud-detection-lakehouse
```

## Bước 2: Cấu hình Gemini API Key

### 2.1. Lấy API Key (MIỄN PHÍ)

1. Truy cập: https://aistudio.google.com/app/apikey
2. Đăng nhập Google
3. Click "Create API Key"
4. Copy API key (dạng: `AIzaSy...`)

### 2.2. Tạo file .env

```bash
# Copy từ template
cp .env.example .env

# Hoặc tạo mới
notepad .env  # Windows
nano .env     # Linux/Mac
```

### 2.3. Paste API Key vào .env

```bash
# File: .env
GOOGLE_API_KEY=AIz

# Optional
MODEL_STAGE=Production
```

## Bước 3: Khởi động services

### Option 1: Full setup (Khuyến nghị)

```bash
docker-compose up -d
```

Chờ 5-10 phút để tất cả services khởi động.

### Option 2: Chỉ chatbot (Nhanh hơn)

```bash
# Start dependencies
docker-compose up -d postgres trino fraud-detection-api

# Start chatbot
docker-compose up -d fraud-chatbot
```

## Bước 4: Verify deployment

### 4.1. Check services

```bash
docker-compose ps
```

**Expected output:**

```
NAME                   STATUS      PORTS
fraud-chatbot          running     0.0.0.0:8501->8501/tcp
fraud-detection-api    running     0.0.0.0:8000->8000/tcp
postgres               running     0.0.0.0:5432->5432/tcp
trino                  running     0.0.0.0:8081->8081/tcp
...
```

### 4.2. Check logs

```bash
# Chatbot logs
docker logs fraud-chatbot --tail 50

# API logs
docker logs fraud-detection-api --tail 50
```

**Expected:** No errors, "You can now view your Streamlit app..."

### 4.3. Test connections

**Chatbot UI:**

```
http://localhost:8501
```

**FastAPI Docs:**

```
http://localhost:8000/docs
```

**Trino UI:**

```
http://localhost:8081
```

## Bước 5: Verify trong Chatbot UI

1. Mở http://localhost:8501
2. Sidebar > System Status:
   - ✅ Gemini API: Connected
   - ✅ ML Model: vX.X.X
3. Click "🧪 Test Gemini" → Should see success message
4. Click "📊 Model Info" → Should see model details
5. Click "🔌 Test Trino" → Should see record count

## Bước 6: Test chatbot

### Test SQL Analytics

```
Top 5 bang có fraud rate cao nhất
```

**Expected:** Agent dùng QueryDatabase, hiển thị bảng kết quả

### Test Prediction

```
Dự đoán giao dịch $850 lúc 2h sáng
```

**Expected:** Agent dùng PredictFraud, hiển thị risk level

### Test Complex Query

```
Check giao dịch $500 và so sánh fraud rate TX
```

**Expected:** Agent dùng cả 2 tools, kết hợp kết quả

---

## ❌ Troubleshooting

### Issue 1: "Gemini API Key chưa config"

**Solution:**

```bash
# Check .env file exists
cat .env  # Linux/Mac
type .env  # Windows

# Make sure GOOGLE_API_KEY is set
grep GOOGLE_API_KEY .env
```

### Issue 2: "API offline"

**Solution:**

```bash
# Restart fraud-detection-api
docker-compose restart fraud-detection-api

# Check logs
docker logs fraud-detection-api -f
```

### Issue 3: "Trino connection failed"

**Solution:**

```bash
# Wait for Trino to be ready (can take 2-3 minutes)
docker logs trino -f

# Restart Trino
docker-compose restart trino
```

### Issue 4: Database tables not found

**Solution:**

```bash
# Re-run postgres init
docker-compose down postgres
docker-compose up -d postgres

# Wait 30 seconds
Start-Sleep -Seconds 30  # PowerShell
sleep 30                  # Bash

# Verify tables
docker exec -it postgres psql -U postgres -d frauddb -c "\dt"
```

**Expected tables:**

- transactions
- fraud_predictions
- chat_history
- producer_checkpoint

### Issue 5: Port already in use

**Solution:**

```bash
# Check what's using the port
netstat -ano | findstr :8501  # Windows
lsof -i :8501                 # Linux/Mac

# Kill process or change port in docker-compose.yml
ports:
  - "8502:8501"  # Change 8501 to 8502
```

---

## 🔄 Update/Redeploy

### Pull latest code

```bash
git pull origin main
```

### Rebuild chatbot

```bash
docker-compose up -d --build fraud-chatbot
```

### Clean rebuild (if needed)

```bash
docker-compose down
docker-compose build --no-cache fraud-chatbot
docker-compose up -d
```

---

## 📊 Database Schema (Auto-created)

Khi khởi động lần đầu, PostgreSQL tự động tạo:

### ✅ transactions

Dữ liệu giao dịch từ CSV

### ✅ fraud_predictions

Kết quả dự đoán từ ML model

- **UNIQUE constraint** trên `trans_num`

### ✅ chat_history

Lịch sử chat của chatbot

- Lưu cả `sql_query` để audit

### ✅ producer_checkpoint

Tracking progress của data producer

**Không cần chạy migrations thủ công!** Init script đã bao gồm tất cả.

---

## 🎯 Next Steps

1. ✅ Upload data: `docker-compose up -d data-producer`
2. ✅ Train model: `docker-compose exec spark bash /app/run_ml_training.sh`
3. ✅ Start streaming: `docker-compose up -d streaming-processor`
4. ✅ Register to Hive: `docker-compose exec spark bash /app/run_register.sh`

---

## 📞 Support

**Logs:**

```bash
docker logs fraud-chatbot -f
```

**Restart all:**

```bash
docker-compose restart
```

**Clean start:**

```bash
docker-compose down -v  # ⚠️ Deletes all data!
docker-compose up -d
```

---

**Setup time:** ~10-15 minutes
**Status check:** http://localhost:8501 → Sidebar → System Status
