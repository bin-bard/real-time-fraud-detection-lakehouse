# Hướng dẫn sử dụng - User Manual

Hướng dẫn sử dụng các tính năng của hệ thống Real-Time Fraud Detection Lakehouse.

---

## Mục lục

1. [AI Chatbot](#1-ai-chatbot)
2. [Real-time Fraud Detection & Slack Alerts](#2-real-time-fraud-detection--slack-alerts)
3. [FastAPI Prediction Service](#3-fastapi-prediction-service)
4. [Dashboards & Monitoring](#4-dashboards--monitoring)
5. [Operations Guide](#5-operations-guide)

---

## 1. AI Chatbot

### Truy cập

URL: **http://localhost:8501**

### Tổng quan

Chatbot hỗ trợ **3 loại câu hỏi**:

1. **SQL Analytics** - Phân tích dữ liệu từ Trino Gold Layer
2. **Fraud Prediction** - Dự đoán gian lận giao dịch mới
3. **General Knowledge** - Câu hỏi về hệ thống, model, lịch sử

---

### 1.1. SQL Analytics (Phân tích dữ liệu)

Chatbot tự động hiểu câu hỏi tiếng Việt/Anh và tạo SQL query.

**Ví dụ câu hỏi:**

```
■ Top 5 bang có tỷ lệ gian lận cao nhất?
■ Merchant nào nguy hiểm nhất?
■ Phân tích fraud patterns theo amount bin
■ Tổng số tiền bị gian lận tuần này?
■ Hiển thị fraud rate theo từng giờ
■ Category nào rủi ro nhất?
■ Có bao nhiêu giao dịch gian lận hôm nay?
```

**Chatbot sẽ:**
1. Hiểu câu hỏi bằng ngôn ngữ tự nhiên
2. Tự động tạo SQL query từ Trino database
3. Thực thi và trả về kết quả với giải thích
4. Hiển thị SQL query đã dùng (trong expander "SQL Query Used")

**Kết quả:**
- Bảng dữ liệu (DataFrame)
- Chart/Plot (nếu phù hợp)
- Giải thích insights

---

### 1.2. Fraud Prediction (Dự đoán gian lận)

Dự đoán xem giao dịch có phải fraud không dựa trên ML model.

**Ví dụ câu hỏi:**

```
■ Dự đoán giao dịch $850 vào lúc 2h sáng
■ Check giao dịch $1200 xa 150km
■ Phân tích giao dịch $50 lúc 14h, category shopping_net
■ Đánh giá giao dịch $300 merchant ABC, 100km
■ Giao dịch online $5000 ở California, khách 55 tuổi
```

**Thông tin cần thiết:**

**Bắt buộc:**
- `amt`: Số tiền giao dịch (USD)

**Tùy chọn (càng nhiều càng chính xác):**
- `hour`: Giờ giao dịch (0-23)
- `distance_km`: Khoảng cách từ địa chỉ khách hàng
- `merchant`: Tên merchant
- `category`: Loại giao dịch (shopping_net, grocery_pos, gas_transport, ...)
- `age`: Tuổi khách hàng
- `city_pop`: Dân số thành phố
- `gender`: Giới tính (M/F)

**Chatbot sẽ:**
1. Trích xuất thông tin giao dịch từ câu hỏi
2. Gọi FastAPI `/predict/explained`
3. Trả về kết quả chi tiết:
   - ✅ **HỢP LỆ** hoặc ⚠️ **GIAN LẬN**
   - Xác suất gian lận (%)
   - Risk level: **LOW** / **MEDIUM** / **HIGH**
   - Giải thích bằng Gemini LLM

**Ví dụ kết quả:**

```
⚠️ GIAN LẬN được phát hiện!

■ Xác suất gian lận: 85.4%
■ Mức độ rủi ro: HIGH
■ Transaction ID: CHAT_1733876543

Phân tích chi tiết:
- Giao dịch có giá trị cao ($850.00) vào lúc 2h sáng (đêm khuya)
- Khoảng cách xa bất thường (150.0 km từ địa chỉ khách hàng)
- Kết hợp các yếu tố trên cho thấy đây là giao dịch nguy hiểm
```

---

### 1.3. General Knowledge (Câu hỏi tổng quát)

**Ví dụ:**

```
■ Model hiện tại có độ chính xác bao nhiêu?
■ Xem thông tin model
■ Lịch sử predictions gần đây
■ 10 predictions mới nhất
■ Gian lận tài chính là gì?
■ Các loại fraud phổ biến?
■ Amount bin là gì?
■ Làm sao phát hiện gian lận?
```

**Kết quả:**
- **Model info**: Version, accuracy, AUC, precision, recall
- **Prediction history**: 10 dự đoán gần nhất từ database
- **Knowledge**: Giải thích từ Gemini LLM

---

### 1.4. Manual Prediction Form

Nếu không muốn dùng chat, có thể nhập trực tiếp vào form.

**Cách sử dụng:**
1. Mở sidebar → **"Manual Prediction Form"**
2. Nhập các thông tin:
   - Amount (bắt buộc)
   - Hour (0-23)
   - Distance (km)
   - Age
   - Category (dropdown)
   - Merchant name
3. Click **"Predict"**
4. Xem kết quả với risk level + explanation

**Lợi ích:**
- Nhanh hơn typing
- Không cần nhớ cú pháp
- Validation tự động

---

### 1.5. CSV Batch Upload

Dự đoán hàng loạt transactions từ file CSV.

**Cách sử dụng:**
1. Mở sidebar → **"CSV Batch Prediction"**
2. Prepare CSV file với các cột:
   ```csv
   amt,hour,distance_km,age,category,merchant
   850.0,2,150.0,45,shopping_net,Merchant_A
   50.0,14,5.0,30,gas_transport,Merchant_B
   1200.0,23,200.0,55,misc_net,Merchant_C
   ```
3. Upload file
4. Click **"Predict All"**
5. Download kết quả (CSV với prediction columns)

**Output columns:**
- Original columns (amt, hour, distance_km, ...)
- `is_fraud_predicted` (0 hoặc 1)
- `fraud_probability` (0.0 - 1.0)
- `risk_level` (LOW/MEDIUM/HIGH)

---

### 1.6. Sidebar Features

**■ Gemini API Status**
- ✅ Connected: API key hợp lệ
- ❌ Failed: Kiểm tra lại key hoặc network

**■ ML Model Info**
- Model version (e.g., `v1.0.20231210`)
- Accuracy, AUC, Precision, Recall
- Training date
- Number of features

**■ Database Connection**
- ✅ Connected: Trino query engine sẵn sàng
- ❌ Failed: Kiểm tra Trino service

**■ Test Connection Button**
- Test Gemini API với prompt mẫu
- Kiểm tra Trino với simple query

---

### 1.7. Session Management

**Lịch sử chat:**
- Mỗi session được lưu vào database (`chat_history` table)
- Session ID tự động tạo
- Có thể xem lại lịch sử: "Lịch sử chat của tôi?"

**Clear chat:**
- Sidebar → "Clear Chat History"
- Xóa messages hiện tại (không xóa database)

**New session:**
- Refresh page (F5)
- Hoặc clear chat và bắt đầu mới

---

## 2. Real-time Fraud Detection & Slack Alerts

### Tổng quan

Hệ thống tự động phát hiện fraud ngay khi transaction được INSERT vào PostgreSQL và gửi alert qua Slack.

### Luồng xử lý

```
Transaction INSERT → PostgreSQL
    ↓ Debezium CDC (< 1ms)
Kafka Topic: postgres.public.transactions
    ↓ Spark Streaming (10-second micro-batch)
Read CDC event → Call FastAPI /predict/raw
    ↓ ML Prediction
Save to fraud_predictions table
    ↓ If is_fraud = 1
Send Slack Alert (ALL risk levels: LOW/MEDIUM/HIGH)
```

**Thời gian phản hồi**: < 1 giây từ INSERT đến Slack notification

---

### 2.1. Khởi động Alert Service

```bash
docker-compose up -d spark-realtime-prediction
```

**Monitor logs:**
```bash
docker logs spark-realtime-prediction --tail 100 -f
```

**Expected output:**
```
INFO - 📊 Batch 123: Processing 25 transactions from CDC events
INFO - Transactions processed: 25
INFO - 💾 Saved prediction to DB: <prediction_id>
INFO - ✅ Slack alert sent: <trans_num> (HIGH)
INFO - 🚨 ALERT sent for <trans_num> (HIGH risk)
```

---

### 2.2. Slack Alert Format

**Cảnh báo gửi đến Slack channel:**

```
🚨 FRAUD ALERT - HIGH RISK 🚨

Transaction Details:
• Trans ID: 8c9d4b5a...
• Amount: $1,247.85
• Customer: John Doe
• Merchant: fraud_Stracke-Lemke
• Location: New York, NY

Risk Assessment:
• Fraud Probability: 89.3%
• Risk Level: HIGH

AI Analysis:
- Giao dịch có giá trị cao ($1,247.85) vào lúc 3h sáng (đêm khuya/sáng sớm)
- Giao dịch xa 184.3km từ địa chỉ khách hàng
- Merchant có tiền tố "fraud_" (nghi ngờ)
```

**Alert Policy:**
- **Gửi tất cả fraud** (không chỉ HIGH risk)
- LOW risk: Màu xanh
- MEDIUM risk: Màu vàng
- HIGH risk: Màu đỏ + emoji cảnh báo

---

### 2.3. Monitoring Predictions

**Xem predictions trong database:**

```bash
docker exec postgres psql -U postgres -d frauddb -c "SELECT * FROM fraud_predictions ORDER BY prediction_time DESC LIMIT 10;"
```

**Query real-time metrics:**

```sql
-- Số lượng fraud predictions hôm nay
SELECT COUNT(*) 
FROM fraud_predictions 
WHERE prediction_time::date = CURRENT_DATE 
  AND is_fraud_predicted = 1;

-- High-risk transactions
SELECT p.trans_num, t.amt, t.merchant, p.prediction_score
FROM fraud_predictions p
JOIN transactions t ON p.trans_num = t.trans_num
WHERE p.is_fraud_predicted = 1 
  AND p.prediction_score > 0.8
ORDER BY p.prediction_time DESC
LIMIT 20;

-- Fraud rate theo giờ
SELECT 
  EXTRACT(HOUR FROM t.trans_date_trans_time) AS hour,
  COUNT(*) AS total_transactions,
  SUM(CASE WHEN p.is_fraud_predicted=1 THEN 1 ELSE 0 END) AS fraud_count,
  ROUND(100.0 * SUM(CASE WHEN p.is_fraud_predicted=1 THEN 1 ELSE 0 END) / COUNT(*), 2) AS fraud_rate
FROM transactions t
LEFT JOIN fraud_predictions p ON t.trans_num = p.trans_num
GROUP BY hour
ORDER BY hour;
```

---

### 2.4. Test Real-time Flow

**Chèn transaction thủ công:**

```bash
docker exec postgres psql -U postgres -d frauddb -c "INSERT INTO transactions (trans_date_trans_time, cc_num, merchant, category, amt, first, last, gender, street, city, state, zip, lat, long, city_pop, job, dob, trans_num, unix_time, merch_lat, merch_long, is_fraud) VALUES (NOW(), 8888888888888888, 'REALTIME_TEST', 'gas_transport', 8888.88, 'Test', 'User', 'F', '999 Test St', 'TestCity', 'NY', 10001, 40.71, -74.00, 500000, 'Tester', '1990-01-01', 'TEST_' || EXTRACT(epoch FROM NOW())::bigint, EXTRACT(epoch FROM NOW())::int, 40.72, -74.01, 1) RETURNING trans_num;"
```

**Expected:**
1. Debezium capture → Kafka (< 1ms)
2. Spark reads CDC event (10s batch)
3. API predicts fraud
4. Save to `fraud_predictions`
5. Slack alert sent

---

### 2.5. Disable/Enable Alerts

**Disable Slack alerts (chỉ save predictions):**
```bash
# Xóa SLACK_WEBHOOK_URL trong .env
# Hoặc comment out
# SLACK_WEBHOOK_URL=

docker-compose up -d --build spark-realtime-prediction
```

**Enable lại:**
```bash
# Uncomment SLACK_WEBHOOK_URL trong .env
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL

docker-compose up -d --build spark-realtime-prediction
```

---

## 3. FastAPI Prediction Service

### Truy cập

URL: **http://localhost:8000**  
Docs: **http://localhost:8000/docs** (Swagger UI)

---

### 3.1. Endpoints

#### GET `/health`

Kiểm tra API health và model status.

**Request:**
```bash
curl http://localhost:8000/health
```

**Response:**
```json
{
  "status": "ok",
  "model_loaded": true,
  "model_version": "v1.0.20231210"
}
```

---

#### GET `/model/info`

Xem thông tin model hiện tại.

**Request:**
```bash
curl http://localhost:8000/model/info
```

**Response:**
```json
{
  "model_name": "fraud_detection_model",
  "model_version": "v1.0.20231210",
  "model_stage": "Production",
  "metrics": {
    "accuracy": 0.968,
    "auc": 0.995,
    "precision": 0.952,
    "recall": 0.931
  },
  "training_date": "2023-12-10T02:00:00Z",
  "features": ["amt", "hour", "distance_km", "age", ...]
}
```

---

#### POST `/predict/raw`

Dự đoán fraud cho 1 transaction (real-time alert service sử dụng).

**Request:**
```bash
curl -X POST http://localhost:8000/predict/raw \
  -H "Content-Type: application/json" \
  -d '{
    "amt": 850.0,
    "hour": 2,
    "distance_km": 150.0,
    "age": 45,
    "category": "shopping_net",
    "merchant": "fraud_TestMerchant",
    "city_pop": 500000
  }'
```

**Response:**
```json
{
  "is_fraud_predicted": 1,
  "fraud_probability": 0.854,
  "risk_level": "HIGH",
  "feature_explanation": "- Giao dịch có giá trị cao ($850.00)\n- Giao dịch vào lúc 2h (đêm khuya)\n- Giao dịch xa 150.0km từ địa chỉ khách hàng"
}
```

---

#### POST `/predict/explained`

Dự đoán fraud với giải thích từ Gemini LLM (chatbot sử dụng).

**Request:**
```bash
curl -X POST http://localhost:8000/predict/explained \
  -H "Content-Type: application/json" \
  -d '{
    "amt": 1200.0,
    "hour": 23,
    "distance_km": 200.0,
    "age": 55,
    "category": "misc_net",
    "merchant": "SuspiciousMerchant"
  }'
```

**Response:**
```json
{
  "is_fraud_predicted": 1,
  "fraud_probability": 0.893,
  "risk_level": "HIGH",
  "llm_explanation": "Đây là giao dịch nguy hiểm vì: (1) số tiền lớn $1200 vào lúc 23h đêm, (2) khoảng cách 200km rất xa so với địa chỉ thường trú, (3) category 'misc_net' là online transaction dễ bị lợi dụng. Khuyến nghị liên hệ khách hàng xác nhận.",
  "transaction_id": "CHAT_1733876543"
}
```

---

#### POST `/predict/batch`

Dự đoán hàng loạt transactions (CSV upload sử dụng).

**Request:**
```bash
curl -X POST http://localhost:8000/predict/batch \
  -H "Content-Type: application/json" \
  -d '{
    "transactions": [
      {"amt": 850.0, "hour": 2, "distance_km": 150.0},
      {"amt": 50.0, "hour": 14, "distance_km": 5.0},
      {"amt": 1200.0, "hour": 23, "distance_km": 200.0}
    ]
  }'
```

**Response:**
```json
{
  "results": [
    {
      "transaction_index": 0,
      "is_fraud_predicted": 1,
      "fraud_probability": 0.854,
      "risk_level": "HIGH"
    },
    {
      "transaction_index": 1,
      "is_fraud_predicted": 0,
      "fraud_probability": 0.123,
      "risk_level": "LOW"
    },
    {
      "transaction_index": 2,
      "is_fraud_predicted": 1,
      "fraud_probability": 0.893,
      "risk_level": "HIGH"
    }
  ],
  "total_processed": 3,
  "fraud_count": 2
}
```

---

### 3.2. Risk Level Thresholds

| Risk Level | Fraud Probability | Mô tả |
|-----------|------------------|-------|
| **LOW** | < 50% | Giao dịch hợp lệ, rủi ro thấp |
| **MEDIUM** | 50% - 80% | Cần theo dõi, có dấu hiệu nghi ngờ |
| **HIGH** | > 80% | Rủi ro cao, gần chắc chắn fraud |

**Lưu ý:** 
- Alert service gửi Slack cho **TẤT CẢ** fraud (kể cả LOW)
- Có thể tùy chỉnh threshold trong code

---

## 4. Dashboards & Monitoring

### 4.1. Airflow (Workflow Orchestration)

**URL**: http://localhost:8081  
**Credentials**: admin / admin

**2 DAGs chính:**

#### lakehouse_pipeline_taskflow
- **Schedule**: Mỗi 5 phút
- **Workflow**:
  1. Bronze → Silver (feature engineering)
  2. Silver → Gold (dimensional modeling)
  3. Optimize Delta tables (compaction, vacuum)

**Trigger manual:**
```bash
docker exec airflow-scheduler airflow dags trigger lakehouse_pipeline_taskflow
```

#### model_retraining_taskflow
- **Schedule**: Hàng ngày 2h sáng
- **Workflow**:
  1. Extract features từ Silver layer
  2. Train RandomForest + LogisticRegression
  3. Evaluate metrics (Accuracy, AUC, Precision, Recall)
  4. Register model to MLflow
  5. Promote to "Production" stage
  6. Reload model trong FastAPI

**Trigger manual:**
```bash
docker exec airflow-scheduler airflow dags trigger model_retraining_taskflow
```

**Monitor DAG runs:**
- Vào Airflow UI → "DAGs"
- Click vào DAG name
- Xem "Graph View" hoặc "Grid View"
- Kiểm tra logs của từng task

---

### 4.2. MLflow (ML Tracking & Registry)

**URL**: http://localhost:5001

**Chức năng:**

#### Experiments
- Xem tất cả training runs
- Compare metrics giữa các runs
- Filter by tags, parameters

#### Models
- Registered models với version history
- Model stages: None → Staging → Production → Archived
- Download model artifacts

#### Metrics
- Accuracy, AUC-ROC, Precision, Recall
- Confusion Matrix (plot)
- Feature importances

**Xem model Production:**
1. Vào "Models" tab
2. Click "fraud_detection_model"
3. Xem version có stage "Production"
4. Download artifacts hoặc xem metrics

---

### 4.3. MinIO (Object Storage)

**URL**: http://localhost:9001  
**Credentials**: minioadmin / minioadmin

**Buckets:**
- `lakehouse/bronze/` - Raw CDC data (Delta Lake)
- `lakehouse/silver/` - Engineered features (Delta Lake)
- `lakehouse/gold/` - Star schema (Delta Lake)
- `lakehouse/checkpoints/` - Spark streaming offsets

**Quản lý:**
- Browse files
- Delete old data
- Monitor storage usage

---

### 4.4. Trino (SQL Query Engine)

**URL**: http://localhost:8085  
**No credentials required**

**Truy vấn qua CLI:**
```bash
docker exec trino trino --catalog delta --schema default
```

**Example queries:**

```sql
-- Show tables
SHOW TABLES;

-- Query Gold layer
SELECT state, COUNT(*) as fraud_count 
FROM fact_transactions 
WHERE is_fraud=1 
GROUP BY state 
ORDER BY fraud_count DESC 
LIMIT 5;

-- Join dimensions
SELECT 
  c.first_name, c.last_name,
  m.merchant_name,
  t.amt,
  t.is_fraud
FROM fact_transactions t
JOIN dim_customer c ON t.customer_id = c.customer_id
JOIN dim_merchant m ON t.merchant_id = m.merchant_id
WHERE t.is_fraud = 1
LIMIT 10;
```

---

### 4.5. PostgreSQL (Direct DB Access)

**Connection:**
- Host: `localhost`
- Port: `5432`
- Database: `frauddb`
- User: `postgres`
- Password: `postgres123`

**Tools:**
- psql (command-line)
- DBeaver (GUI)
- pgAdmin (GUI)

**Useful queries:**

```sql
-- Recent predictions
SELECT * FROM fraud_predictions 
ORDER BY prediction_time DESC 
LIMIT 20;

-- Fraud rate today
SELECT 
  COUNT(*) AS total,
  SUM(CASE WHEN is_fraud=1 THEN 1 ELSE 0 END) AS fraud_count,
  ROUND(100.0 * SUM(CASE WHEN is_fraud=1 THEN 1 ELSE 0 END) / COUNT(*), 2) AS fraud_rate
FROM transactions
WHERE trans_date_trans_time::date = CURRENT_DATE;

-- Chat history
SELECT * FROM chat_history 
ORDER BY timestamp DESC 
LIMIT 10;
```

---

## 5. Operations Guide

### 5.1. Start/Stop Services

**Start all:**
```bash
docker-compose up -d
```

**Stop all:**
```bash
docker-compose down
```

**Start specific service:**
```bash
docker-compose up -d <service_name>
```

**Stop specific service:**
```bash
docker-compose stop <service_name>
```

**Restart service:**
```bash
docker-compose restart <service_name>
```

**Rebuild and restart:**
```bash
docker-compose up -d --build <service_name>
```

---

### 5.2. Restart Streaming Services

Khi cần reset checkpoint hoặc fix lỗi:

```bash
# Stop streaming services
docker-compose stop spark-streaming spark-realtime-prediction

# Remove checkpoints (optional - reset offset)
docker exec minio mc rm -r --force minio/lakehouse/checkpoints/

# Restart
docker-compose up -d spark-streaming spark-realtime-prediction
```

**Script helper (PowerShell):**
```bash
# Trong folder scripts/
.\restart-streaming-services.ps1
```

---

### 5.3. View Logs

**Real-time logs (follow):**
```bash
docker logs <service_name> --tail 100 -f
```

**Last N lines:**
```bash
docker logs <service_name> --tail 50
```

**Specific time range:**
```bash
docker logs <service_name> --since 10m
docker logs <service_name> --since 2023-12-10T10:00:00
```

**Save logs to file:**
```bash
docker logs <service_name> > logs.txt 2>&1
```

---

### 5.4. Backup & Recovery

#### Backup PostgreSQL

```bash
# Full database backup
docker exec postgres pg_dump -U postgres frauddb > backup_frauddb_$(date +%Y%m%d).sql

# Specific table
docker exec postgres pg_dump -U postgres -t transactions frauddb > backup_transactions.sql
```

#### Restore PostgreSQL

```bash
# Drop and recreate
docker exec postgres psql -U postgres -c "DROP DATABASE frauddb;"
docker exec postgres psql -U postgres -c "CREATE DATABASE frauddb;"

# Restore from backup
docker exec -i postgres psql -U postgres frauddb < backup_frauddb_20231210.sql
```

#### Backup Delta Lake

```bash
# Copy từ MinIO
docker exec minio mc mirror minio/lakehouse /backup/lakehouse_$(date +%Y%m%d)
```

#### Backup MLflow Models

```bash
# Export models từ MLflow artifact store
# Models được lưu tại: mlruns/ folder trong container
docker cp mlflow:/mlflow/mlruns ./backup/mlruns_$(date +%Y%m%d)
```

---

### 5.5. Cleanup & Maintenance

**Remove stopped containers:**
```bash
docker-compose rm -f
```

**Remove old images:**
```bash
docker image prune -a
```

**Remove unused volumes:**
```bash
docker volume prune
```

**Clean all (RESET EVERYTHING):**
```bash
docker-compose down -v
docker system prune -a --volumes
```

**Optimize Delta tables:**
```bash
# Chạy DAG optimize task
docker exec airflow-scheduler airflow dags trigger lakehouse_pipeline_taskflow
```

---

### 5.6. Monitoring Resource Usage

**Container stats:**
```bash
docker stats
```

**Disk usage:**
```bash
docker system df
```

**Network usage:**
```bash
docker network inspect real-time-fraud-detection-lakehouse_default
```

---

## Troubleshooting Quick Reference

| Vấn đề | Giải pháp |
|--------|----------|
| **Chatbot không kết nối Gemini** | Kiểm tra `GEMINI_API_KEY` trong `.env`, test tại sidebar |
| **Slack alert 404** | Tạo webhook mới, update `.env`, rebuild service |
| **Model chưa train** | Trigger `model_retraining_taskflow` DAG |
| **Prediction time sai timezone** | Đổi PostgreSQL timezone hoặc code |
| **Services không start** | Kiểm tra logs, tăng RAM Docker, free disk space |
| **Bronze layer empty** | Chạy data producer hoặc bulk load |
| **Trino query timeout** | Tăng `query.max-execution-time` trong config |

➜ Chi tiết: **[Developer Guide - Troubleshooting](DEVELOPER_GUIDE.md#troubleshooting)**

---

**Tài liệu khác:**
- [Setup Guide](SETUP.md) - Cài đặt hệ thống
- [Architecture](ARCHITECTURE.md) - Kiến trúc 6 tầng
- [Developer Guide](DEVELOPER_GUIDE.md) - Code structure, optimization
- [Changelog](CHANGELOG.md) - Bug fixes, FAQ
