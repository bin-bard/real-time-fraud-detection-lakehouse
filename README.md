# Real-Time Fraud Detection Lakehouse

> Hệ thống Data Lakehouse phát hiện gian lận thẻ tín dụng theo thời gian thực với kiến trúc 6 lớp: CDC → Bronze → Silver → Gold → Query → ML/API

![Architecture](docs/architecture.png)

---

## Tổng quan dự án

Dự án xây dựng pipeline xử lý dữ liệu end-to-end phát hiện gian lận thẻ tín dụng, kết hợp streaming real-time và batch processing với công nghệ Data Lakehouse hiện đại.

### Tính năng chính

▸ **CDC Real-time Streaming**: PostgreSQL → Debezium → Kafka → Bronze Layer (< 1 giây)
▸ **ETL Batch Processing**: Bronze → Silver → Gold (Delta Lake, Airflow mỗi 5 phút)
▸ **Machine Learning**: Huấn luyện tự động RandomForest + LogisticRegression (hàng ngày 2h sáng)
▸ **Real-time Fraud Detection**: Spark Streaming → FastAPI ML Prediction → Slack Alert (< 1s)
▸ **AI Chatbot**: Streamlit + LangChain + Gemini API (hỏi đáp tiếng Việt, dự đoán fraud, phân tích SQL)
▸ **Interactive Dashboards**: Trino + Metabase + MLflow + Airflow monitoring

### Mục tiêu

- Phát hiện gian lận thẻ tín dụng với độ chính xác cao (**96.8% accuracy, 99.5% AUC**)
- Xử lý real-time với độ trễ thấp (**< 1 giây** từ transaction đến alert)
- Kiến trúc mở rộng dễ dàng với **Delta Lake ACID transactions**
- Giao diện thân thiện (Chatbot tiếng Việt, Manual Form, CSV Batch Upload)

---

## Bắt đầu nhanh

### Yêu cầu hệ thống

| Thành phần   | Yêu cầu tối thiểu                | Khuyến nghị    |
| ------------ | -------------------------------- | -------------- |
| **CPU**      | 6 cores                          | 8+ cores       |
| **RAM**      | 10 GB                            | 16 GB          |
| **Disk**     | 30 GB free                       | 50 GB free     |
| **Software** | Docker 24+, Docker Compose 2.20+ | Docker Desktop |

### Cài đặt trong 3 bước

**Bước 1: Clone và cấu hình**

```bash
git clone https://github.com/bin-bard/real-time-fraud-detection-lakehouse.git
cd real-time-fraud-detection-lakehouse

# Tạo file .env từ template
cp .env.example .env

# Chỉnh sửa .env và thêm Gemini API key
# Lấy key miễn phí tại: https://aistudio.google.com/app/apikey
# GEMINI_API_KEY=your_api_key_here
# SLACK_WEBHOOK_URL=your_slack_webhook_url  # Optional
```

**Bước 2: Khởi động hệ thống**

```bash
# Khởi động tất cả services (16 containers)
docker-compose up -d

# Đợi 3-5 phút để các services khởi động
# PostgreSQL sẽ tự động tạo database schema
```

**Bước 3: Load dữ liệu và huấn luyện model**

```bash
# Load 50,000 transactions mẫu (bulk load - nhanh)
docker exec data-producer python producer.py --bulk-load 50000

# Huấn luyện ML model (hoặc đợi Airflow DAG chạy tự động vào 2h sáng)
docker exec airflow-scheduler airflow dags trigger model_retraining_taskflow
```

**Hoàn tất!** Truy cập các dashboard:

- **Chatbot**: http://localhost:8501 (Chat tiếng Việt, dự đoán fraud)
- **Airflow**: http://localhost:8081 (admin/admin - Monitor DAGs)
- **MLflow**: http://localhost:5001 (Theo dõi model training)
- **Fraud API**: http://localhost:8000/docs (FastAPI prediction endpoint)
- **MinIO**: http://localhost:9001 (minioadmin/minioadmin - Object storage)
- **Trino**: http://localhost:8085 (SQL query engine)

➜ Chi tiết đầy đủ: **[Hướng dẫn cài đặt chi tiết](docs/SETUP.md)**

---

## Kiến trúc hệ thống

### Lược đồ 6 tầng

```
┌─────────────────────────────────────────────────────────┐
│              USER INTERFACES                            │
│  Streamlit │ Metabase │ Airflow │ MLflow │ FastAPI     │
└────────────┬────────────────────────────────────────────┘
             │
┌────────────▼────────────────────────────────────────────┐
│          LAYER 6: ML & API                              │
│  MLflow Registry │ FastAPI Prediction │ Airflow Training│
└────────────┬────────────────────────────────────────────┘
             │
┌────────────▼────────────────────────────────────────────┐
│         LAYER 5: QUERY LAYER                            │
│  Trino (SQL Engine) │ Hive Metastore (Optional Cache)  │
└────────────┬────────────────────────────────────────────┘
             │
┌────────────▼────────────────────────────────────────────┐
│         LAYER 4: GOLD LAYER                             │
│  Star Schema (Delta Lake)                               │
│  • dim_customer, dim_merchant, dim_location             │
│  • dim_category, fact_transactions                      │
└────────────┬────────────────────────────────────────────┘
             │
┌────────────▼────────────────────────────────────────────┐
│        LAYER 3: SILVER LAYER                            │
│  Engineered Features (40+ features)                     │
│  Delta Lake (s3a://lakehouse/silver)                   │
└────────────┬────────────────────────────────────────────┘
             │
┌────────────▼────────────────────────────────────────────┐
│        LAYER 2: BRONZE LAYER                            │
│  Raw CDC Data (22 columns) │ Delta Lake ACID           │
│  Spark Streaming (10-second micro-batches)             │
└────────────┬────────────────────────────────────────────┘
             │
┌────────────▼────────────────────────────────────────────┐
│       LAYER 1: CDC INGESTION                            │
│  PostgreSQL → Debezium (CDC) → Kafka (Streaming)       │
└─────────────────────────────────────────────────────────┘
```

➜ Chi tiết kiến trúc: **[Architecture Documentation](docs/ARCHITECTURE.md)**

---

## Công nghệ sử dụng

| Lớp                | Công nghệ                      | Phiên bản  | Cổng       | Mô tả                         |
| ------------------ | ------------------------------ | ---------- | ---------- | ----------------------------- |
| **Data Source**    | PostgreSQL                     | 14         | 5432       | OLTP database với CDC enabled |
| **CDC**            | Debezium                       | 2.5        | 8083       | Change Data Capture connector |
| **Streaming**      | Apache Kafka                   | 3.5        | 9092       | Message broker                |
| **Processing**     | Apache Spark                   | 3.4.1      | 8080       | Streaming + Batch             |
| **Storage**        | Delta Lake + MinIO             | 2.4 / 2023 | 9000, 9001 | ACID Lakehouse                |
| **Metastore**      | Hive Metastore                 | 3.1.3      | 9083       | Metadata cache (optional)     |
| **Query Engine**   | Trino                          | 428        | 8085       | Distributed SQL               |
| **Orchestration**  | Apache Airflow                 | 2.8.0      | 8081       | Workflow scheduler            |
| **ML Tracking**    | MLflow                         | 2.8.0      | 5001       | Model versioning              |
| **Prediction API** | FastAPI                        | 0.104      | 8000       | Real-time ML inference        |
| **Chatbot**        | Streamlit + LangChain + Gemini | -          | 8501       | AI assistant (Vietnamese)     |
| **BI Dashboard**   | Metabase                       | -          | 3000       | Business intelligence         |

---

## Tài liệu

### Cho người dùng

- **[Hướng dẫn cài đặt (Setup Guide)](docs/SETUP.md)** → Cài đặt từ đầu, cấu hình, load data, troubleshooting
- **[Hướng dẫn sử dụng (User Manual)](docs/USER_MANUAL.md)** → Chatbot, Real-time Alerts, API, Dashboards

### Cho lập trình viên

- **[Kiến trúc hệ thống (Architecture)](docs/ARCHITECTURE.md)** → 6-layer architecture, data flow, schema
- **[Developer Guide](docs/DEVELOPER_GUIDE.md)** → Code structure, optimization, troubleshooting, FAQ
- **[Changelog](docs/CHANGELOG.md)** → Lịch sử thay đổi, bug fixes

---

## Các tính năng nổi bật

### 1. Real-time Fraud Detection & Slack Alerts

Phát hiện gian lận trong < 1 giây và gửi cảnh báo tức thì:

- **Luồng**: Transaction → CDC → Kafka → Spark → ML → Slack
- **Policy**: Cảnh báo **TẤT CẢ** fraud (LOW/MEDIUM/HIGH)
- **Thông tin**: Trans ID, Amount, Customer, Risk Level, Probability, Explanation

```bash
# Khởi động Real-time Detection
docker-compose up -d spark-realtime-prediction
```

### 2. AI Chatbot (Tiếng Việt)

Hỗ trợ 3 loại câu hỏi:

**■ SQL Analytics**

```
"Top 5 bang có tỷ lệ gian lận cao nhất?"
"Tổng giá trị giao dịch mỗi bang?"
```

**■ Fraud Prediction**

```
"Dự đoán giao dịch $850 lúc 2h sáng, cách nhà 150km"
"Giao dịch online $1200 tại California"
```

**■ General Knowledge**

```
"Model có độ chính xác bao nhiêu?"
"Lịch sử dự đoán của tôi?"
```

**Công cụ bổ sung:**

- Manual Prediction Form (nhập liệu thân thiện)
- CSV Batch Upload (dự đoán hàng loạt)

### 3. Machine Learning Pipeline

- **Thuật toán**: RandomForest + LogisticRegression (ensemble)
- **Features**: 20 engineered features (amount, distance, time, demographics)
- **Class balancing**: SMOTE oversampling (1:1 ratio)
- **Performance**: 96.8% accuracy, 99.5% AUC-ROC
- **Training**: Tự động hàng ngày 2h sáng (Airflow DAG)
- **Tracking**: MLflow experiment tracking + model registry

### 4. Data Lakehouse với Delta Lake

- **ACID Transactions**: Consistency cho concurrent reads/writes
- **Time Travel**: Query historical data với `@v1` syntax
- **Schema Evolution**: Thêm/sửa columns không downtime
- **Upsert/Merge**: Update/insert efficient với `MERGE INTO`
- **Optimizations**: Z-ordering, file compaction, vacuum

### 5. Batch ETL Pipeline (Airflow)

**DAG: `lakehouse_pipeline_taskflow`** (Mỗi 5 phút)

```
Bronze Streaming → Silver Cleaning → Gold Aggregation → Optimize
```

**DAG: `model_retraining_taskflow`** (Hàng ngày 2h sáng)

```
Extract Features → Train → Evaluate → Register MLflow → Deploy API
```

---

## Hiệu năng hệ thống

| Metric                   | Giá trị            | Ghi chú                          |
| ------------------------ | ------------------ | -------------------------------- |
| **ML Accuracy**          | 96.8%              | RandomForest on balanced dataset |
| **AUC-ROC**              | 99.5%              | Excellent discrimination         |
| **Prediction Latency**   | < 100ms            | FastAPI inference time           |
| **End-to-end Latency**   | < 1s               | Transaction → Slack Alert        |
| **Streaming Throughput** | 200-500 tx/batch   | 10-second micro-batches          |
| **Data Volume**          | 1.2M+ transactions | Sparkov dataset                  |
| **Fraud Rate**           | 0.5-1%             | Realistic imbalanced data        |

---

## Troubleshooting nhanh

**Services không khởi động?**

```bash
docker-compose logs -f [service_name]  # Xem logs
docker-compose restart [service_name]   # Restart
```

**Chatbot không kết nối Gemini?**

- Kiểm tra `GEMINI_API_KEY` trong `.env`
- Test tại sidebar "Gemini API Status"
- Lấy key miễn phí: https://aistudio.google.com/app/apikey

**Slack alerts lỗi 404 - no_service?**

- Webhook URL không hợp lệ hoặc đã bị xóa
- Tạo webhook mới: https://api.slack.com/apps → Incoming Webhooks
- Cập nhật `SLACK_WEBHOOK_URL` trong `.env`
- Rebuild: `docker-compose up -d --build spark-realtime-prediction`

**ML Model chưa train?**

```bash
# Trigger manual training
docker exec airflow-scheduler airflow dags trigger model_retraining_taskflow
```

**Prediction time sai timezone?**

- PostgreSQL mặc định dùng UTC
- Chỉnh timezone trong code hoặc database config
- Xem: `docker exec postgres psql -U postgres -c "SHOW timezone;"`

➜ Xem thêm: **[Troubleshooting Guide chi tiết](docs/DEVELOPER_GUIDE.md#troubleshooting)**

---

## Cấu trúc thư mục

```
real-time-fraud-detection-lakehouse/
├── airflow/                  # Airflow DAGs (ETL + ML training)
│   └── dags/
├── config/                   # Spark, Trino, Hive configuration
├── data/                     # Raw CSV datasets (1.2M transactions)
├── database/                 # PostgreSQL init scripts
├── deployment/               # Dockerfiles & setup scripts
├── docs/                     # Documentation
├── notebooks/                # Jupyter notebooks (EDA, experiments)
├── scripts/                  # PowerShell helper scripts
├── services/
│   ├── data-producer/        # Transaction stream simulator
│   ├── fraud-chatbot/        # Streamlit + LangChain chatbot
│   └── fraud-detection-api/  # FastAPI ML inference service
├── spark/                    # Spark jobs (streaming, batch, ML)
│   └── app/
└── sql/                      # Gold layer views & test queries
```

---

## Đóng góp và phát triển

### Local Development

**Chạy Chatbot local (hot reload):**

```bash
cd services/fraud-chatbot
pip install -r requirements.txt
streamlit run src/main.py
```

**Test FastAPI local:**

```bash
cd services/fraud-detection-api
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

➜ Xem thêm: **[Developer Guide](docs/DEVELOPER_GUIDE.md)**

---

## Liên hệ

- **Repository**: https://github.com/bin-bard/real-time-fraud-detection-lakehouse
- **Issues**: https://github.com/bin-bard/real-time-fraud-detection-lakehouse/issues

---

**Bắt đầu ngay**: [Hướng dẫn cài đặt chi tiết →](docs/SETUP.md)
