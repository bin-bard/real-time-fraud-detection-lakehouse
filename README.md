# Real-Time Fraud Detection Lakehouse

<div align="center">

**Hệ thống Data Lakehouse phát hiện gian lận thẻ tín dụng theo thời gian thực**

![Architecture Diagram](docs/architecture.png)

**Kiến trúc 6 lớp**: `CDC` → `Bronze` → `Silver` → `Gold` → `Query` → `ML/API`

[🚀 Bắt đầu nhanh](#-bắt-đầu-nhanh) • [📚 Tài liệu](#-tài-liệu) • [🌟 Tính năng](#-các-tính-năng-nổi-bật) • [⚡ Hiệu năng](#-hiệu-năng-hệ-thống)

</div>

---

## 📋 Tổng quan

Hệ thống end-to-end phát hiện gian lận thẻ tín dụng, kết hợp **streaming real-time** và **batch processing** với kiến trúc Data Lakehouse hiện đại.

**Điểm nổi bật:**

- ⚡ Phát hiện gian lận **< 1 giây** từ transaction đến Slack alert
- 🧠 Machine Learning với **92.8% accuracy, 98.4% AUC-ROC**
- 💡 AI Chatbot tiếng Việt với Gemini API
- 🏗 Kiến trúc Delta Lake ACID với 1.2M+ transactions

### ▶ Tính năng nổi bật

| Tính năng                     | Mô tả                                         | Hiệu năng    |
| ------------------------------- | ----------------------------------------------- | -------------- |
| ⚡**CDC Streaming**       | PostgreSQL → Debezium → Kafka → Bronze Layer | < 1 giây      |
| ⚙**ETL Pipeline**        | Bronze → Silver → Gold (Delta Lake + Airflow) | Mỗi 5 phút   |
| 🧠**Machine Learning**    | RandomForest + LogisticRegression tự động    | 92.8% accuracy |
| 🔔**Real-time Detection** | Spark Streaming → ML → Slack Alert            | < 1 giây      |
| 💡**AI Chatbot**          | Streamlit + LangChain + Gemini (Tiếng Việt)   | Tức thì      |
| 📈**Dashboards**          | Trino + Metabase + MLflow + Airflow             | Interactive    |

### 🎖 Mục tiêu dự án

- ► Phát hiện gian lận với độ chính xác cao: **92.8% accuracy, 98.4% AUC-ROC**
- ► Xử lý real-time với độ trễ thấp: **< 1 giây** từ transaction đến alert
- ► Kiến trúc mở rộng dễ dàng với **Delta Lake ACID transactions**
- ► Giao diện thân thiện: Chatbot tiếng Việt, Manual Form, CSV Batch Upload

---

## 🚀 Bắt đầu nhanh

### 🖥 Yêu cầu hệ thống

| Thành phần       | Tối thiểu                      | Khuyến nghị  |
| ------------------ | -------------------------------- | -------------- |
| **CPU**      | 6 cores                          | 8+ cores       |
| **RAM**      | 10 GB                            | 16 GB          |
| **Disk**     | 30 GB free                       | 50 GB free     |
| **Software** | Docker 24+, Docker Compose 2.20+ | Docker Desktop |

### ⚡ Cài đặt nhanh

```bash
# 1. Clone repository
git clone https://github.com/bin-bard/real-time-fraud-detection-lakehouse.git
cd real-time-fraud-detection-lakehouse

# 2. Cấu hình environment
cp .env.example .env
# Chỉnh sửa .env:
# - GEMINI_API_KEY=your_key (lấy tại: https://aistudio.google.com/app/apikey)
# - SLACK_WEBHOOK_URL=your_webhook (optional)

# 3. Khởi động hệ thống (16 containers)
docker-compose up -d

# 4. Load dữ liệu mẫu (50,000 transactions)
docker exec data-producer python producer.py --bulk-load 50000

# 5. Huấn luyện ML model
docker exec airflow-scheduler airflow dags trigger model_retraining_taskflow
```

**⏱ Thời gian**: ~5-10 phút (tùy cấu hình máy)

### ✅ Hoàn tất! Truy cập các dashboard

| Service               | URL                        | Credentials           | Mô tả                             |
| --------------------- | -------------------------- | --------------------- | ----------------------------------- |
| 💡**Chatbot**   | http://localhost:8501      | -                     | Chat tiếng Việt, dự đoán fraud |
| ⚙**Airflow**   | http://localhost:8081      | admin/admin           | Monitor DAGs                        |
| 📈**MLflow**    | http://localhost:5001      | -                     | Theo dõi model training            |
| 🔗**Fraud API** | http://localhost:8000/docs | -                     | FastAPI prediction endpoint         |
| 📦**MinIO**     | http://localhost:9001      | minioadmin/minioadmin | Object storage                      |
| 🔎**Trino**     | http://localhost:8085      | -                     | SQL query engine                    |

> 📘 **Chi tiết đầy đủ**: [Hướng dẫn cài đặt chi tiết](docs/SETUP.md)

---

## 🏗 Kiến trúc 6 lớp

| Lớp                        | Công nghệ                   | Chức năng                                  |
| --------------------------- | ----------------------------- | -------------------------------------------- |
| **Layer 6: ML & API** | MLflow + FastAPI + Airflow    | Model training, registry, prediction API     |
| **Layer 5: Query**    | Trino + Hive Metastore        | Distributed SQL query engine                 |
| **Layer 4: Gold**     | Delta Lake (Star Schema)      | Dimensional model: dim_* + fact_transactions |
| **Layer 3: Silver**   | Delta Lake + Spark            | Feature engineering (40+ features)           |
| **Layer 2: Bronze**   | Delta Lake + Spark Streaming  | Raw CDC data (10-second micro-batches)       |
| **Layer 1: CDC**      | PostgreSQL + Debezium + Kafka | Change Data Capture streaming                |

> 📘 **Chi tiết**: [Architecture Documentation](docs/ARCHITECTURE.md) • [Developer Guide](docs/DEVELOPER_GUIDE.md)

---

## 🛠 Tech Stack

<table>
<tr>
<td><strong>Category</strong></td>
<td><strong>Technology</strong></td>
<td><strong>Version</strong></td>
<td><strong>Port</strong></td>
</tr>
<tr>
<td>🗄 <strong>Data Source</strong></td>
<td>PostgreSQL</td>
<td>14</td>
<td>5432</td>
</tr>
<tr>
<td>🔄 <strong>CDC</strong></td>
<td>Debezium</td>
<td>2.5</td>
<td>8083</td>
</tr>
<tr>
<td>📡 <strong>Streaming</strong></td>
<td>Apache Kafka</td>
<td>3.5</td>
<td>9092</td>
</tr>
<tr>
<td>⚡ <strong>Processing</strong></td>
<td>Apache Spark</td>
<td>3.4.1</td>
<td>8080</td>
</tr>
<tr>
<td>🏗 <strong>Storage</strong></td>
<td>Delta Lake + MinIO</td>
<td>2.4 / 2023</td>
<td>9000, 9001</td>
</tr>
<tr>
<td>🔎 <strong>Query Engine</strong></td>
<td>Trino</td>
<td>428</td>
<td>8085</td>
</tr>
<tr>
<td>⚙ <strong>Orchestration</strong></td>
<td>Apache Airflow</td>
<td>2.8.0</td>
<td>8081</td>
</tr>
<tr>
<td>📈 <strong>ML Tracking</strong></td>
<td>MLflow</td>
<td>2.8.0</td>
<td>5001</td>
</tr>
<tr>
<td>🔗 <strong>API</strong></td>
<td>FastAPI</td>
<td>0.104</td>
<td>8000</td>
</tr>
<tr>
<td>💡 <strong>Chatbot</strong></td>
<td>Streamlit + LangChain + Gemini</td>
<td>Latest</td>
<td>8501</td>
</tr>
<tr>
<td>📊 <strong>BI Dashboard</strong></td>
<td>Metabase</td>
<td>Latest</td>
<td>3000</td>
</tr>
</table>

---

## 📚 Tài liệu

### 👤 Cho người dùng

- **[Hướng dẫn cài đặt (Setup Guide)](docs/SETUP.md)** → Cài đặt từ đầu, cấu hình, load data, troubleshooting
- **[Hướng dẫn sử dụng (User Manual)](docs/USER_MANUAL.md)** → Chatbot, Real-time Alerts, API, Dashboards

### 👨‍💻 Cho lập trình viên

- **[Kiến trúc hệ thống (Architecture)](docs/ARCHITECTURE.md)** → 6-layer architecture, data flow, schema
- **[Developer Guide](docs/DEVELOPER_GUIDE.md)** → Code structure, optimization, troubleshooting, FAQ
- **[Changelog](docs/CHANGELOG.md)** → Lịch sử thay đổi, bug fixes

---

## 🌟 Tính năng chi tiết

### 🔔 1. Real-time Fraud Detection & Slack Alerts

**Luồng xử lý**: Transaction → CDC → Kafka → Spark → ML → Slack (< 1 giây)

```bash
# Khởi động real-time detection
docker-compose up -d spark-realtime-prediction
```

- Cảnh báo **TẤT CẢ** fraud (LOW/MEDIUM/HIGH)
- Thông tin: Trans ID, Amount, Customer, Risk Level, Probability
- File: `spark/app/realtime_prediction_job.py`
- Setup: Cấu hình `SLACK_WEBHOOK_URL` trong `.env`

### 💡 2. AI Chatbot (Tiếng Việt)

**3 chế độ hỏi đáp:**

| Chế độ                    | Ví dụ câu hỏi                                            |
| ---------------------------- | ------------------------------------------------------------ |
| 📊**SQL Analytics**    | "Top 5 bang có tỷ lệ gian lận cao nhất?"                |
| 🎯**Fraud Prediction** | "Dự đoán giao dịch $850 lúc 2h sáng, cách nhà 150km" |
| 💬**General Q&A**      | "Model có độ chính xác bao nhiêu?"                     |

**Công cụ bổ sung**: Manual Form • CSV Batch Upload • Prediction History

### 🧠 3. Machine Learning Pipeline

| Component             | Detail                                                        |
| --------------------- | ------------------------------------------------------------- |
| **Algorithms**  | RandomForest (200 trees) + LogisticRegression                 |
| **Features**    | 15 engineered features (amount, distance, time, demographics) |
| **Balancing**   | Random undersampling (1:1 ratio)                              |
| **Performance** | 92.8% accuracy, 98.4% AUC-ROC                                 |
| **Training**    | Auto daily at 2 AM (Airflow DAG)                              |
| **Tracking**    | MLflow experiment + model registry                            |

### 🏗 4. Delta Lake Features

- **ACID Transactions** - Consistency cho concurrent operations
- **Time Travel** - Query historical data: `SELECT * FROM table@v1`
- **Schema Evolution** - Add/modify columns zero-downtime
- **Upsert/Merge** - Efficient `MERGE INTO` operations
- **Optimizations** - Z-ordering, compaction, vacuum

### ⚙ 5. Airflow DAGs

**`lakehouse_pipeline_taskflow`** (Every 5 minutes)

```
Bronze → Silver → Gold → Optimize
```

**`model_retraining_taskflow`** (Daily 2 AM)

```
Extract → Train → Evaluate → Register → Deploy
```

---

## ⚡ Hiệu năng hệ thống

| Metric                         | Giá trị          | Ghi chú                         |
| ------------------------------ | ------------------ | -------------------------------- |
| **ML Accuracy**          | 92.8%              | RandomForest on balanced dataset |
| **AUC-ROC**              | 98.4%              | Excellent discrimination         |
| **Prediction Latency**   | < 100ms            | FastAPI inference time           |
| **End-to-end Latency**   | < 1s               | Transaction → Slack Alert       |
| **Streaming Throughput** | 200-500 tx/batch   | 10-second micro-batches          |
| **Data Volume**          | 1.2M+ transactions | Sparkov dataset                  |
| **Fraud Rate**           | 0.5-1%             | Realistic imbalanced data        |

---

## 🔧 Troubleshooting

<details>
<summary><strong>❌ Services không khởi động?</strong></summary>

```bash
docker-compose logs -f [service_name]  # Xem logs
docker-compose restart [service_name]   # Restart service
docker-compose down && docker-compose up -d  # Full restart
```

</details>

<details>
<summary><strong>🤖 Chatbot không kết nối Gemini?</strong></summary>

- Kiểm tra `GEMINI_API_KEY` trong `.env`
- Test tại sidebar "Gemini API Status"
- Lấy key miễn phí: https://aistudio.google.com/app/apikey
- Rebuild: `docker-compose up -d --build fraud-chatbot`

</details>

<details>
<summary><strong>🔔 Slack alerts lỗi 404?</strong></summary>

- Webhook URL không hợp lệ hoặc đã xóa
- Tạo webhook mới: https://api.slack.com/apps → Incoming Webhooks
- Cập nhật `SLACK_WEBHOOK_URL` trong `.env`
- Rebuild: `docker-compose up -d --build spark-realtime-prediction`

</details>

<details>
<summary><strong>🧠 ML Model chưa train?</strong></summary>

```bash
# Trigger manual training
docker exec airflow-scheduler airflow dags trigger model_retraining_taskflow

# Check training status
docker exec airflow-scheduler airflow dags list-runs -d model_retraining_taskflow
```

</details>

<details>
<summary><strong>⏰ Prediction time sai timezone?</strong></summary>

```bash
# Check PostgreSQL timezone
docker exec postgres psql -U postgres -c "SHOW timezone;"

# Set timezone in docker-compose.yml
environment:
  - TZ=Asia/Ho_Chi_Minh
```

</details>

> 📘 **Chi tiết**: [Troubleshooting Guide](docs/DEVELOPER_GUIDE.md#troubleshooting)

---

## 📁 Cấu trúc dự án

```
📦 real-time-fraud-detection-lakehouse/
├── 🔄 airflow/dags/              # ETL + ML training DAGs
├── ⚙ config/                     # Spark, Trino, Hive configs
├── 📊 data/                      # Raw CSV (1.2M transactions)
├── 🗄 database/                  # PostgreSQL init scripts
├── 🐳 deployment/                # Dockerfiles & setup
├── 📚 docs/                      # Documentation
├── 📓 notebooks/                 # Jupyter EDA & experiments
├── 🔧 scripts/                   # PowerShell helpers
├── 🎯 services/
│   ├── data-producer/           # Transaction simulator
│   ├── fraud-chatbot/           # Streamlit AI chatbot
│   └── fraud-detection-api/     # FastAPI ML service
├── ⚡ spark/app/                 # Streaming, batch, ML jobs
└── 🔎 sql/                       # Gold layer views & queries
```

---

## 🔨 Đóng góp và phát triển

### 💻 Local Development

**▸ Chạy Chatbot local (hot reload):**

```bash
cd services/fraud-chatbot
pip install -r requirements.txt
streamlit run src/main.py
```

**▸ Test FastAPI local:**

```bash
cd services/fraud-detection-api
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

> 📘 **Xem thêm**: [Developer Guide](docs/DEVELOPER_GUIDE.md)

---

## 📞 Liên hệ

- **Repository**: https://github.com/bin-bard/real-time-fraud-detection-lakehouse
- **Issues**: https://github.com/bin-bard/real-time-fraud-detection-lakehouse/issues

---

<div align="center">

**Bắt đầu ngay**: [Hướng dẫn cài đặt chi tiết →](docs/SETUP.md)

</div>
