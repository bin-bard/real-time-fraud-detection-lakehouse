# Real-Time Fraud Detection Lakehouse

Hệ thống Data Lakehouse phát hiện gian lận thẻ tín dụng theo thời gian thực sử dụng Delta Lake + Apache Spark + Trino + Machine Learning.

---

## Tính năng chính

- **Real-time CDC Pipeline**: PostgreSQL → Debezium → Kafka → Delta Lake với streaming liên tục
- **Lakehouse Architecture**: Delta Lake với ACID transactions, Time Travel, và Schema Evolution
- **Hybrid Processing**: Streaming (Bronze layer) + Batch ETL (Silver/Gold layers qua Airflow)
- **ML Training tự động**: RandomForest + LogisticRegression với MLflow tracking (hàng ngày 2 AM)
- **Interactive Analytics**: Trino query engine + Metabase BI dashboard
- **AI Chatbot**: Streamlit + LangChain + Gemini AI (chat với database bằng tiếng Việt)

---

## Quick Start

### 1. Clone và cấu hình

```bash
git clone https://github.com/bin-bard/real-time-fraud-detection-lakehouse.git
cd real-time-fraud-detection-lakehouse

# Tạo file .env cho Chatbot (tùy chọn)
cp .env.example .env
# Thêm GOOGLE_API_KEY vào .env (lấy miễn phí từ https://aistudio.google.com/app/apikey)
```

### 2. Khởi động hệ thống

```bash
docker compose up -d --build
```

Đợi 5-10 phút để tất cả services khởi tạo.

### 3. Load dữ liệu và verify

```bash
# Bulk load 50K giao dịch (~250 fraud samples)
docker exec data-producer python producer.py --bulk-load 50000

# Verify dữ liệu
docker exec trino trino --server localhost:8081 --execute "SELECT COUNT(*) FROM delta.bronze.transactions"
```

**Truy cập dashboards:**

- Airflow: http://localhost:8081 (`admin` / `admin`)
- MLflow: http://localhost:5001
- MinIO: http://localhost:9001 (`minio` / `minio123`)
- Chatbot: http://localhost:8501

Chi tiết: [docs/SETUP.md](docs/SETUP.md)

---

## Kiến trúc tổng quan

```
┌─────────────────────────────────────────────────────────────┐
│ Layer 1: CDC Ingestion                                      │
│ PostgreSQL → Debezium → Kafka → Bronze Streaming            │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Layer 2: Bronze (Raw Data Lake)                            │
│ Delta Lake @ s3a://lakehouse/bronze/                        │
│ Format: Parquet + _delta_log/ (ACID + Time Travel)         │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Layer 3: Silver (Curated + Feature Engineering)            │
│ Delta Lake @ s3a://lakehouse/silver/                        │
│ 40+ features: geographic, demographic, time, amount         │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Layer 4: Gold (Star Schema - 5 tables)                     │
│ Delta Lake @ s3a://lakehouse/gold/                          │
│ 4 Dimensions: customer, merchant, time, location           │
│ 1 Fact: transactions (NO physical constraints)             │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Layer 5: Query & Consumption                               │
│ Trino (Delta catalog) + Metabase BI                        │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Layer 6: ML & API                                           │
│ Airflow (orchestration) + MLflow (tracking) + FastAPI      │
└─────────────────────────────────────────────────────────────┘
```

Chi tiết: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

---

## Tài liệu

| Tài liệu                                           | Mô tả                                                           |
| ---------------------------------------------------- | ----------------------------------------------------------------- |
| **[SETUP.md](docs/SETUP.md)**                     | Hướng dẫn cài đặt từ đầu, configuration, troubleshooting |
| **[USER_MANUAL.md](docs/USER_MANUAL.md)**         | Hướng dẫn sử dụng Chatbot, FastAPI, Dashboards               |
| **[ARCHITECTURE.md](docs/ARCHITECTURE.md)**       | Kiến trúc chi tiết, data flow, schema, ML pipeline             |
| **[DEVELOPER_GUIDE.md](docs/DEVELOPER_GUIDE.md)** | Development setup, code structure, bug fixes, FAQ                 |
| **[CHANGELOG.md](docs/CHANGELOG.md)**             | Lịch sử phiên bản (historical reference)                      |

---

## Tech Stack

| Component               | Technology         | Port       | Mô tả                      |
| ----------------------- | ------------------ | ---------- | ---------------------------- |
| **Database**      | PostgreSQL 14      | 5432       | OLTP source với CDC enabled |
| **CDC**           | Debezium 2.5       | 8083       | Change Data Capture          |
| **Streaming**     | Apache Kafka       | 9092       | Message broker               |
| **Processing**    | Spark 3.4.1        | 8080       | Stream + batch processing    |
| **Storage**       | Delta Lake + MinIO | 9000, 9001 | ACID lakehouse               |
| **Metastore**     | Hive 3.1.3         | 9083       | Metadata cache (optional)    |
| **Query Engine**  | Trino              | 8085       | Distributed SQL engine       |
| **Orchestration** | Airflow 2.8.0      | 8081       | Workflow scheduler           |
| **ML Tracking**   | MLflow 2.8.0       | 5001       | Model registry & experiments |
| **BI Dashboard**  | Metabase           | 3000       | Business intelligence        |
| **API**           | FastAPI 3.0        | 8000       | Real-time prediction service |
| **Chatbot**       | Streamlit + Gemini | 8501       | AI chatbot (tiếng Việt)    |

**Yêu cầu hệ thống:**

- CPU: 6 cores minimum (8+ khuyến nghị)
- RAM: 10GB minimum (16GB khuyến nghị)
- Disk: 30GB free space
- Docker Desktop 4.0+ hoặc Docker Engine 20.10+

---

## Troubleshooting nhanh

### 1. Service không khởi động được

```bash
# Kiểm tra logs
docker logs <service-name> --tail 50

# Restart service
docker compose restart <service-name>

# Reset hoàn toàn (XÓA DỮ LIỆU)
docker compose down -v
docker compose up -d --build
```

### 2. Không có dữ liệu trong Silver/Gold

```bash
# Kiểm tra Bronze có dữ liệu
docker exec trino trino --server localhost:8081 --execute "SELECT COUNT(*) FROM delta.bronze.transactions"

# Trigger Airflow DAG manually
# Truy cập http://localhost:8081 → lakehouse_pipeline_taskflow → Trigger DAG
```

### 3. ML training chỉ có ~15-20 samples

**Đây là hành vi bình thường!** Fraud rate thực tế = 0.5% → Cần nhiều giao dịch để có đủ fraud samples.

**Giải pháp:** Bulk load 50K giao dịch

```bash
docker exec data-producer python producer.py --bulk-load 50000
```

### 4. Chatbot lỗi "API key not provided"

```bash
# Tạo .env file với Gemini API key
cp .env.example .env
# Thêm GOOGLE_API_KEY=AIzaSy... vào .env

# Restart chatbot
docker compose restart fraud-chatbot
```

Chi tiết: [docs/DEVELOPER_GUIDE.md](docs/DEVELOPER_GUIDE.md) → Section Troubleshooting

---

## Lưu ý quan trọng

**Gold Layer constraints:**

- Gold layer sử dụng Delta Lake → **KHÔNG có physical constraints** (PK/FK/Unique)
- Đây là best practice của Lakehouse architecture (tối ưu cho big data analytics)
- Data quality được đảm bảo bằng ETL logic, không phải database constraints

**Alert System:**

- FastAPI trả về `risk_level: HIGH/MEDIUM/LOW` ✅
- NHƯNG KHÔNG tự động gửi email/Slack ❌
- Cần tự implement notification nếu cần (xem [docs/USER_MANUAL.md](docs/USER_MANUAL.md))

**SQL Views:**

- File `sql/gold_layer_views_delta.sql` chứa 9 analytical views
- Views CHƯA được execute tự động → Cần chạy thủ công trong Trino
- Chi tiết: [docs/USER_MANUAL.md](docs/USER_MANUAL.md) → Section Dashboard & Monitoring
