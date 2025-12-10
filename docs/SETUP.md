# Hướng dẫn cài đặt - Setup Guide

Hướng dẫn cài đặt hệ thống Real-Time Fraud Detection Lakehouse từ đầu.

---

## Mục lục

1. [Yêu cầu hệ thống](#yêu-cầu-hệ-thống)
2. [Quick Start (3 bước)](#quick-start)
3. [Cài đặt chi tiết](#cài-đặt-chi-tiết)
4. [Cấu hình Gemini API](#cấu-hình-gemini-api)
5. [Real-time Detection Setup](#real-time-detection-setup)
6. [Dashboard Access](#dashboard-access)
7. [Verification & Testing](#verification--testing)
8. [Troubleshooting](#troubleshooting)

---

## Yêu cầu hệ thống

### Phần cứng

| Thành phần  | Tối thiểu       | Khuyến nghị | Ghi chú                        |
| ----------- | --------------- | ----------- | ------------------------------ |
| **CPU**     | 6 cores         | 8+ cores    | Spark + Airflow cần multi-core |
| **RAM**     | 10 GB           | 16 GB       | Spark executors chiếm 4-6GB    |
| **Disk**    | 30 GB free      | 50 GB free  | Delta Lake + Docker images     |
| **Network** | Stable Internet | High-speed  | Download Docker images (~10GB) |

### Phần mềm

- **Docker**: Version 24.0+ (Bắt buộc)
- **Docker Compose**: Version 2.20+ (Bắt buộc)
- **Git**: Version 2.x+ (Bắt buộc)
- **PowerShell** (Windows) hoặc **Bash** (Linux/Mac)
- **Gemini API Key** (Miễn phí - cho Chatbot)
- **Slack Webhook URL** (Tùy chọn - cho Real-time Alerts)

---

## Quick Start

### 3 bước khởi động hệ thống

**Bước 1: Clone và cấu hình**

```bash
# Clone repository
git clone https://github.com/bin-bard/real-time-fraud-detection-lakehouse.git
cd real-time-fraud-detection-lakehouse

# Tạo file .env từ template
cp .env.example .env

# Chỉnh sửa .env và thêm Gemini API key
# Lấy key miễn phí tại: https://aistudio.google.com/app/apikey
notepad .env  # Windows
nano .env     # Linux/Mac
```

**Bước 2: Khởi động services**

```bash
# Khởi động tất cả 16 services
docker-compose up -d

# Đợi 3-5 phút để các services khởi động hoàn toàn
# PostgreSQL sẽ tự động tạo database schema (init_postgres.sql)
```

**Bước 3: Load dữ liệu & Train model**

```bash
# Option A: Bulk load 50K transactions (Nhanh - 10 giây)
docker exec postgres psql -U postgres -d frauddb -c "\COPY transactions(trans_date_trans_time, cc_num, merchant, category, amt, first, last, gender, street, city, state, zip, lat, long, city_pop, job, dob, trans_num, unix_time, merch_lat, merch_long, is_fraud) FROM '/data/fraudTrain.csv' WITH (FORMAT csv, HEADER true, DELIMITER ',') LIMIT 50000;"

# Trigger ML training (hoặc đợi tự động chạy vào 2h sáng)
docker exec airflow-scheduler airflow dags trigger model_retraining_taskflow
```

**Hoàn tất!** Truy cập:

- Chatbot: http://localhost:8501
- Airflow: http://localhost:8081 (admin/admin)
- MLflow: http://localhost:5001

---

## Cài đặt chi tiết

### 1. Clone repository

```bash
git clone https://github.com/bin-bard/real-time-fraud-detection-lakehouse.git
cd real-time-fraud-detection-lakehouse
```

### 2. Cấu hình file .env

Hệ thống sử dụng **1 file `.env` duy nhất** tại root folder.

```bash
# Tạo từ template
cp .env.example .env
```

**Nội dung file .env cần thiết:**

```bash
# ============ GEMINI API (Bắt buộc cho Chatbot) ============
GEMINI_API_KEY=your_gemini_api_key_here

# ============ PostgreSQL ============
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=frauddb
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres123

# ============ MinIO (Object Storage) ============
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=minioadmin
MINIO_ENDPOINT=http://minio:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin

# ============ Kafka ============
KAFKA_BOOTSTRAP_SERVERS=kafka:9092

# ============ Trino ============
TRINO_HOST=trino
TRINO_PORT=8085

# ============ MLflow ============
MLFLOW_TRACKING_URI=http://mlflow:5000
MODEL_STAGE=Production

# ============ Slack Alerts (Tùy chọn) ============
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL

# ============ API ============
API_HOST=fraud-detection-api
API_PORT=8000
```

**Lưu ý:**

- `GEMINI_API_KEY`: **Bắt buộc** để Chatbot hoạt động
- `SLACK_WEBHOOK_URL`: Tùy chọn, nếu không có thì bỏ trống (Real-time alerts sẽ không gửi Slack)
- Các biến khác giữ nguyên giá trị mặc định

---

## Cấu hình Gemini API

### Lấy API Key miễn phí

1. Truy cập: https://aistudio.google.com/app/apikey
2. Đăng nhập bằng Google Account
3. Click **"Create API Key"**
4. Chọn project (hoặc tạo mới)
5. Copy API key (dạng: `AIzaSy...`)

### Paste vào file .env

```bash
GEMINI_API_KEY=AIzaSyXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
```

### Test API Key

Sau khi khởi động Chatbot, kiểm tra tại sidebar:

- ✅ **Gemini API Status**: Connected
- Nếu lỗi: Kiểm tra lại API key hoặc network

---

## 3. Khởi động services

### Option 1: Khởi động toàn bộ (Khuyến nghị)

```bash
docker-compose up -d
```

**16 services sẽ được khởi động:**

1. **postgres** - OLTP database (5432)
2. **zookeeper** - Kafka coordination
3. **kafka** - Message broker (9092)
4. **debezium-connect** - CDC connector (8083)
5. **minio** - Object storage (9000, 9001)
6. **hive-metastore** - Metadata cache (9083) [Optional]
7. **spark-streaming** - Bronze layer streaming
8. **spark-silver** - Silver layer batch job
9. **spark-gold** - Gold layer batch job
10. **spark-realtime-prediction** - Real-time alert service
11. **trino** - Query engine (8085)
12. **mlflow** - ML tracking (5001)
13. **fraud-detection-api** - Prediction API (8000)
14. **fraud-chatbot** - Streamlit chatbot (8501)
15. **airflow-scheduler** - Workflow orchestration
16. **airflow-webserver** - Airflow UI (8081)

### Option 2: Khởi động từng nhóm

**A. Core services (Database + Storage)**

```bash
docker-compose up -d postgres minio kafka zookeeper debezium-connect
```

**B. Processing layer**

```bash
docker-compose up -d spark-streaming spark-silver spark-gold
```

**C. ML & API**

```bash
docker-compose up -d mlflow fraud-detection-api
```

**D. Chatbot only**

```bash
docker-compose up -d fraud-chatbot
```

### Thời gian khởi động

| Service           | Thời gian | Ghi chú                          |
| ----------------- | --------- | -------------------------------- |
| PostgreSQL        | 5-10s     | Tự động chạy `init_postgres.sql` |
| Kafka + Zookeeper | 15-20s    |                                  |
| Debezium          | 30-40s    | Tự động tạo CDC connector        |
| MinIO             | 5s        | Tự động tạo bucket `lakehouse`   |
| Spark services    | 20-30s    |                                  |
| Airflow           | 60-90s    | Init database + DAGs             |
| API + Chatbot     | 10-15s    | Load ML model                    |

**Tổng thời gian**: 3-5 phút cho toàn bộ hệ thống.

---

## 4. Verify services

### Kiểm tra trạng thái containers

```bash
docker-compose ps
```

**Expected output:**

```
NAME                        STATE       PORTS
postgres                    Up          0.0.0.0:5432->5432/tcp
kafka                       Up          0.0.0.0:9092->9092/tcp
debezium-connect            Up          0.0.0.0:8083->8083/tcp
minio                       Up          0.0.0.0:9000-9001->9000-9001/tcp
trino                       Up          0.0.0.0:8085->8085/tcp
fraud-detection-api         Up          0.0.0.0:8000->8000/tcp
fraud-chatbot               Up          0.0.0.0:8501->8501/tcp
airflow-webserver           Up          0.0.0.0:8081->8081/tcp
mlflow                      Up          0.0.0.0:5001->5000/tcp
...
```

### Health checks

**PostgreSQL database schema:**

```bash
docker exec postgres psql -U postgres -d frauddb -c "\dt"
```

Expected tables:

- `transactions` (Main OLTP table)
- `fraud_predictions` (ML prediction results)
- `producer_checkpoint` (Streaming offset tracking)
- `chat_history` (Chatbot conversation history)

**Kafka topics:**

```bash
docker exec kafka kafka-topics.sh --bootstrap-server localhost:9092 --list
```

Expected: `postgres.public.transactions` (CDC topic)

**Debezium connector:**

```bash
curl http://localhost:8083/connectors/postgres-connector/status
```

Expected: `"state": "RUNNING"`

**API health:**

```bash
curl http://localhost:8000/health
```

Expected: `{"status": "ok", "model_loaded": true}`

**MinIO buckets:**

```bash
docker exec minio mc ls minio/lakehouse/
```

Expected: `bronze/`, `silver/`, `gold/`, `checkpoints/`

---

## 5. Load dữ liệu

Có **3 cách** để load dữ liệu vào hệ thống:

### Option A: Bulk Load (Khuyến nghị - Nhanh nhất)

Load 50,000 transactions trong ~10 giây:

```bash
docker exec postgres psql -U postgres -d frauddb -c "\COPY transactions(trans_date_trans_time, cc_num, merchant, category, amt, first, last, gender, street, city, state, zip, lat, long, city_pop, job, dob, trans_num, unix_time, merch_lat, merch_long, is_fraud) FROM '/data/fraudTrain.csv' WITH (FORMAT csv, HEADER true, DELIMITER ',') LIMIT 50000;"
```

**Lưu ý:**

- Transactions được INSERT trực tiếp vào PostgreSQL
- Debezium CDC sẽ tự động capture và gửi vào Kafka
- Spark streaming sẽ ghi vào Bronze layer

### Option B: Streaming Load (Mô phỏng real-time)

Chạy data producer để stream từng transaction:

```bash
# Chạy producer với tốc độ 10 tx/giây
docker-compose up -d data-producer
```

**Producer configuration:**

- File: `services/data-producer/producer.py`
- Tốc độ mặc định: 10 transactions/giây
- Checkpoint: Tự động lưu offset, có thể resume

**Monitor producer:**

```bash
docker logs data-producer --tail 50 -f
```

**Dừng producer:**

```bash
docker-compose stop data-producer
```

### Option C: Auto-load (Load toàn bộ dataset)

Load tất cả 1.2M transactions (chậm - ~20 phút):

```bash
docker exec postgres psql -U postgres -d frauddb -c "\COPY transactions(trans_date_trans_time, cc_num, merchant, category, amt, first, last, gender, street, city, state, zip, lat, long, city_pop, job, dob, trans_num, unix_time, merch_lat, merch_long, is_fraud) FROM '/data/fraudTrain.csv' WITH (FORMAT csv, HEADER true, DELIMITER ',');"
```

**Cảnh báo**: Load toàn bộ sẽ tạo hàng triệu CDC events, có thể làm chậm hệ thống.

---

## 6. Train ML Model

Có **2 cách** để train model:

### Option A: Trigger manual (Ngay lập tức)

```bash
# Trigger Airflow DAG
docker exec airflow-scheduler airflow dags trigger model_retraining_taskflow

# Monitor DAG run
docker exec airflow-scheduler airflow dags list-runs -d model_retraining_taskflow
```

**Thời gian training**: 5-10 phút (tùy số lượng transactions)

### Option B: Automatic (Đợi schedule)

Airflow DAG `model_retraining_taskflow` tự động chạy **hàng ngày vào 2h sáng**.

**Schedule:**

```python
schedule_interval="0 2 * * *"  # Cron: 2:00 AM daily
```

**Không cần làm gì**, model sẽ tự động:

1. Extract features từ Silver layer
2. Train RandomForest + LogisticRegression
3. Evaluate metrics (Accuracy, AUC, Precision, Recall)
4. Register model vào MLflow
5. Promote to "Production" stage
6. Reload model trong FastAPI

---

## Real-time Detection Setup

### Khởi động Real-time Alert Service

```bash
# Start Spark Streaming alert service
docker-compose up -d spark-realtime-prediction
```

### Luồng xử lý Real-time

```
Transaction INSERT → PostgreSQL
    ↓ Debezium CDC
Kafka Topic: postgres.public.transactions
    ↓ Spark Streaming (10-second micro-batch)
Read CDC event → Call FastAPI /predict/raw
    ↓ ML Prediction
Save to fraud_predictions table
    ↓ If is_fraud = 1
Send Slack Alert (ALL risk levels: LOW/MEDIUM/HIGH)
```

### Cấu hình Slack Webhook

**1. Tạo Slack Incoming Webhook:**

- Truy cập: https://api.slack.com/apps
- Chọn app (hoặc tạo mới)
- "Incoming Webhooks" → "Add New Webhook to Workspace"
- Chọn channel để nhận alerts
- Copy Webhook URL

**2. Cập nhật .env:**

```bash
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR_WORKSPACE_ID/YOUR_CHANNEL_ID/YOUR_TOKEN
```

**3. Rebuild service:**

```bash
docker-compose up -d --build spark-realtime-prediction
```

### Test Real-time Flow

**Chèn transaction thủ công để test:**

```bash
docker exec postgres psql -U postgres -d frauddb -c "INSERT INTO transactions (trans_date_trans_time, cc_num, merchant, category, amt, first, last, gender, street, city, state, zip, lat, long, city_pop, job, dob, trans_num, unix_time, merch_lat, merch_long, is_fraud) VALUES (NOW(), 8888888888888888, 'REALTIME_TEST', 'gas_transport', 8888.88, 'Test', 'User', 'F', '999 Test St', 'TestCity', 'NY', 10001, 40.71, -74.00, 500000, 'Tester', '1990-01-01', 'TEST_' || EXTRACT(epoch FROM NOW())::bigint, EXTRACT(epoch FROM NOW())::int, 40.72, -74.01, 1) RETURNING trans_num, amt, is_fraud;"
```

**Expected:**

1. Debezium capture change → Kafka
2. Spark reads CDC event
3. API predicts fraud
4. Save to `fraud_predictions` table
5. Slack alert sent (nếu có webhook)

**Check logs:**

```bash
docker logs spark-realtime-prediction --tail 100 -f
```

Expected output:

```
INFO - 💾 Saved prediction to DB: <prediction_id>
INFO - ✅ Slack alert sent: <trans_num> (HIGH)
INFO - 🚨 ALERT sent for <trans_num> (HIGH risk)
```

---

## Dashboard Access

### Tất cả các URLs và credentials

| Service        | URL                        | Credentials             | Mô tả                             |
| -------------- | -------------------------- | ----------------------- | --------------------------------- |
| **Chatbot**    | http://localhost:8501      | -                       | Streamlit AI Chatbot (tiếng Việt) |
| **Airflow**    | http://localhost:8081      | admin / admin           | Workflow orchestration            |
| **MLflow**     | http://localhost:5001      | -                       | ML experiment tracking            |
| **FastAPI**    | http://localhost:8000/docs | -                       | Swagger API documentation         |
| **MinIO**      | http://localhost:9001      | minioadmin / minioadmin | Object storage console            |
| **Trino**      | http://localhost:8085      | -                       | SQL query engine                  |
| **Kafka UI**   | -                          | -                       | Not included (optional: AKHQ)     |
| **Metabase**   | http://localhost:3000      | -                       | BI Dashboard (if configured)      |
| **PostgreSQL** | localhost:5432             | postgres / postgres123  | Direct DB access (psql, DBeaver)  |

### Chatbot Features

**Truy cập**: http://localhost:8501

**Sidebar kiểm tra:**

- ✅ Gemini API Status
- ✅ ML Model Info (version, accuracy, AUC)
- ✅ Database Connection

**3 loại câu hỏi:**

1. **SQL Analytics**: "Top 5 bang có fraud rate cao nhất?"
2. **Fraud Prediction**: "Dự đoán $850 lúc 2h sáng, 150km"
3. **General Knowledge**: "Lịch sử dự đoán của tôi?"

**Công cụ bổ sung:**

- Manual Prediction Form
- CSV Batch Upload

### Airflow DAGs

**Truy cập**: http://localhost:8081 (admin/admin)

**2 DAGs chính:**

1. **lakehouse_pipeline_taskflow**: ETL Bronze → Silver → Gold (Mỗi 5 phút)
2. **model_retraining_taskflow**: ML training (Hàng ngày 2h sáng)

**Trigger manual:**

```bash
docker exec airflow-scheduler airflow dags trigger lakehouse_pipeline_taskflow
docker exec airflow-scheduler airflow dags trigger model_retraining_taskflow
```

### MLflow Tracking

**Truy cập**: http://localhost:5001

**Xem:**

- Experiments: Model training runs
- Models: Registered models với version history
- Metrics: Accuracy, AUC, Precision, Recall
- Artifacts: Model files, confusion matrix plots

**Model stages:**

- `None`: Newly trained
- `Staging`: Testing
- `Production`: Active (FastAPI sử dụng)
- `Archived`: Old versions

---

## Verification & Testing

### 1. Kiểm tra Database

```bash
# Số lượng transactions
docker exec postgres psql -U postgres -d frauddb -c "SELECT COUNT(*) FROM transactions;"

# Số lượng fraud predictions
docker exec postgres psql -U postgres -d frauddb -c "SELECT COUNT(*) FROM fraud_predictions;"

# Fraud rate
docker exec postgres psql -U postgres -d frauddb -c "SELECT ROUND(100.0 * SUM(CASE WHEN is_fraud=1 THEN 1 ELSE 0 END) / COUNT(*), 2) AS fraud_rate_pct FROM transactions;"
```

### 2. Kiểm tra Delta Lake

```bash
# List Bronze tables
docker exec minio mc ls minio/lakehouse/bronze/

# List Silver tables
docker exec minio mc ls minio/lakehouse/silver/

# List Gold tables
docker exec minio mc ls minio/lakehouse/gold/
```

### 3. Test Trino Queries

```bash
# Show catalogs
docker exec trino trino --execute "SHOW CATALOGS;"

# Show tables in delta catalog
docker exec trino trino --catalog delta --schema default --execute "SHOW TABLES;"

# Query Gold layer
docker exec trino trino --catalog delta --schema default --execute "SELECT state, COUNT(*) as fraud_count FROM fact_transactions WHERE is_fraud=1 GROUP BY state ORDER BY fraud_count DESC LIMIT 5;"
```

### 4. Test API Endpoints

**Health check:**

```bash
curl http://localhost:8000/health
```

**Model info:**

```bash
curl http://localhost:8000/model/info
```

**Predict single transaction:**

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

### 5. Test Chatbot

**Truy cập**: http://localhost:8501

**Test queries:**

```
1. "Top 5 bang có tỷ lệ gian lận cao nhất?"
2. "Dự đoán giao dịch $850 lúc 2h sáng cách nhà 150km"
3. "Model hiện tại có độ chính xác bao nhiêu?"
```

**Expected:**

- Câu 1: Trả về bảng SQL results
- Câu 2: Trả về prediction với risk level + explanation
- Câu 3: Trả về model metrics từ MLflow

---

## Troubleshooting

### 1. Services không khởi động

**Lỗi: "port already allocated"**

```bash
# Kiểm tra port đang sử dụng
netstat -ano | findstr :8501  # Windows
lsof -i :8501                 # Linux/Mac

# Giải quyết: Dừng process hoặc đổi port trong docker-compose.yml
```

**Lỗi: "insufficient memory"**

```bash
# Tăng RAM cho Docker Desktop
# Settings → Resources → Memory → Increase to 8GB+
```

**Lỗi: "no space left on device"**

```bash
# Dọn dẹp Docker
docker system prune -a --volumes
```

### 2. PostgreSQL không tạo tables

**Kiểm tra init script:**

```bash
docker logs postgres | grep "init_postgres.sql"
```

**Expected**: "CREATE TABLE transactions", "CREATE TABLE fraud_predictions"

**Nếu không thấy:**

```bash
# Xóa volume và restart
docker-compose down -v
docker-compose up -d postgres
```

### 3. Debezium không tạo CDC connector

**Kiểm tra connector:**

```bash
curl http://localhost:8083/connectors
```

**Nếu rỗng:**

```bash
# Tạo connector thủ công
docker exec -it debezium-connect curl -X POST -H "Content-Type: application/json" --data @/config/connector-config.json http://localhost:8083/connectors
```

### 4. Spark jobs failed

**Kiểm tra logs:**

```bash
docker logs spark-streaming --tail 100
docker logs spark-silver --tail 100
docker logs spark-gold --tail 100
```

**Lỗi thường gặp:**

- "Connection refused to MinIO" → Kiểm tra MinIO running
- "Table not found" → Chạy Bronze job trước
- "Out of memory" → Tăng RAM cho Docker

### 5. ML Model không load

**Lỗi: "No model found in Production stage"**

```bash
# Trigger model training
docker exec airflow-scheduler airflow dags trigger model_retraining_taskflow

# Kiểm tra MLflow
curl http://localhost:5001/api/2.0/mlflow/registered-models/get?name=fraud_detection_model
```

**Nếu model tồn tại nhưng không load:**

```bash
# Restart API
docker-compose restart fraud-detection-api
docker logs fraud-detection-api
```

### 6. Chatbot không kết nối Gemini

**Lỗi: "Invalid API key"**

- Kiểm tra `GEMINI_API_KEY` trong `.env`
- Lấy key mới tại: https://aistudio.google.com/app/apikey

**Lỗi: "Connection timeout"**

- Kiểm tra network/firewall
- Test: `curl https://generativelanguage.googleapis.com/`

**Rebuild chatbot:**

```bash
docker-compose up -d --build fraud-chatbot
```

### 7. Slack alerts không gửi (404 - no_service)

**Nguyên nhân**: Webhook URL không hợp lệ hoặc đã bị xóa

**Giải quyết:**

1. Tạo webhook mới: https://api.slack.com/apps → Incoming Webhooks
2. Cập nhật `SLACK_WEBHOOK_URL` trong `.env`
3. Rebuild: `docker-compose up -d --build spark-realtime-prediction`

**Test webhook:**

```bash
curl -X POST $SLACK_WEBHOOK_URL \
  -H "Content-Type: application/json" \
  -d '{"text":"Test alert from Fraud Detection System"}'
```

### 8. Prediction time sai timezone

**Lỗi**: `prediction_time` trong database là UTC nhưng local time là GMT+7

**Nguyên nhân**: PostgreSQL mặc định dùng UTC

**Giải quyết Option 1** (Đổi timezone PostgreSQL):

```bash
docker exec postgres psql -U postgres -c "ALTER DATABASE frauddb SET timezone TO 'Asia/Ho_Chi_Minh';"
docker-compose restart postgres
```

**Giải quyết Option 2** (Đổi trong code):

```python
# Trong spark/app/realtime_prediction_job.py
# Thay NOW() bằng:
prediction_time = CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Ho_Chi_Minh'
```

### 9. Airflow DAGs không chạy

**Lỗi: "DAG not found"**

```bash
# List DAGs
docker exec airflow-scheduler airflow dags list

# Nếu không thấy DAG
docker-compose restart airflow-scheduler airflow-webserver
```

**Lỗi: "Executor timeout"**

- Tăng RAM cho Docker
- Giảm số task concurrent trong `airflow.cfg`

### 10. Trino query timeout

**Lỗi: "Query exceeded maximum time"**

```bash
# Tăng timeout trong trino config
# File: config/trino/config.properties
# query.max-execution-time=10m
```

---

## Useful Commands

### Docker Management

```bash
# Xem logs service
docker logs <service_name> --tail 100 -f

# Restart service
docker-compose restart <service_name>

# Rebuild service
docker-compose up -d --build <service_name>

# Stop all services
docker-compose down

# Stop and remove volumes (RESET EVERYTHING)
docker-compose down -v

# View resource usage
docker stats
```

### Database Commands

```bash
# Vào PostgreSQL shell
docker exec -it postgres psql -U postgres -d frauddb

# Truncate table
docker exec postgres psql -U postgres -d frauddb -c "TRUNCATE TABLE transactions, fraud_predictions CASCADE;"

# Export query result to CSV
docker exec postgres psql -U postgres -d frauddb -c "\COPY (SELECT * FROM fraud_predictions LIMIT 100) TO '/tmp/predictions.csv' CSV HEADER;"
```

### Airflow Commands

```bash
# Trigger DAG
docker exec airflow-scheduler airflow dags trigger <dag_id>

# List DAG runs
docker exec airflow-scheduler airflow dags list-runs -d <dag_id>

# Pause/unpause DAG
docker exec airflow-scheduler airflow dags pause <dag_id>
docker exec airflow-scheduler airflow dags unpause <dag_id>
```

### MinIO Commands

```bash
# List buckets
docker exec minio mc ls minio/

# List objects in bucket
docker exec minio mc ls minio/lakehouse/bronze/

# Remove old checkpoints (reset streaming)
docker exec minio mc rm -r --force minio/lakehouse/checkpoints/
```

---

## Next Steps

Sau khi hoàn thành setup:

1. ✅ **Đọc User Manual**: [USER_MANUAL.md](USER_MANUAL.md) - Hướng dẫn sử dụng Chatbot, API, Dashboards
2. ✅ **Tìm hiểu Architecture**: [ARCHITECTURE.md](ARCHITECTURE.md) - Kiến trúc 6 tầng, data flow
3. ✅ **Development**: [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md) - Code structure, optimization
4. ✅ **Troubleshooting**: [CHANGELOG.md](CHANGELOG.md) - Bug fixes history, FAQ

---

**Gặp vấn đề?** Mở issue tại: https://github.com/bin-bard/real-time-fraud-detection-lakehouse/issues
