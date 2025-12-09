# ⚡ Quick Start - Fraud Chatbot 2.0

## 🚀 Deploy ngay (3 bước)

### 1️⃣ Chạy migrations

```powershell
cd C:\Users\thanh\Desktop\Nam4\Ki1\TLCN\real-time-fraud-detection-lakehouse
.\scripts\run-migrations.ps1
```

### 2️⃣ Deploy chatbot

```powershell
.\scripts\deploy-chatbot.ps1
```

### 3️⃣ Truy cập

```
http://localhost:8501
```

---

## 💬 Test nhanh

### SQL Analytics

```
Top 5 bang có fraud rate cao nhất
```

### Prediction

```
Dự đoán giao dịch $850 lúc 2h sáng
```

### Complex

```
Check giao dịch $500 và so sánh fraud rate trung bình TX
```

---

## 🛠️ Tools mới

### Manual Form

1. Sidebar → Tools → Manual Prediction
2. Nhập thông tin giao dịch
3. Click "Dự đoán"

### CSV Batch

1. Sidebar → Tools → Batch Upload
2. Download template → Điền data
3. Upload → Click "Batch Predict"

---

## 🔍 Debug

### Xem logs

```powershell
docker logs fraud-chatbot -f
```

### Restart

```powershell
docker-compose restart fraud-chatbot
```

### Rebuild

```powershell
.\scripts\deploy-chatbot.ps1 -CleanBuild
```

---

## ✅ Verify

### Check database

```sql
-- Chat history có SQL queries
SELECT COUNT(*) FROM chat_history WHERE sql_query IS NOT NULL;

-- Predictions được lưu
SELECT COUNT(*) FROM fraud_predictions;
```

---

## 📋 Changelog

### ✨ Tính năng mới

- ✅ LangChain Agent (ReAct pattern)
- ✅ Manual Prediction Form
- ✅ CSV Batch Upload
- ✅ SQL Query Tracking
- ✅ Fraud Predictions Storage

### 🔧 Fix

- ✅ `chat_history.sql_query` không còn NULL
- ✅ `fraud_predictions` table có data
- ✅ UNIQUE constraint tránh duplicate

### 🏗️ Refactor

- ✅ Tách 1251 dòng → 15 modules
- ✅ Modular architecture
- ✅ Better code organization

---

📚 **Chi tiết:** Xem `CHATBOT_IMPROVEMENTS_SUMMARY.md`
