# Hệ thống Phát hiện Gian lận Thời gian Thực - Data Lakehouse

Hệ thống Data Lakehouse phát hiện gian lận thẻ tín dụng theo thời gian thực sử dụng **Delta Lake** + **Apache Spark** + **Trino**.

![Kiến trúc hệ thống](docs/architecture.png)

## 🎯 Tổng quan

Dự án xây dựng pipeline xử lý dữ liệu end-to-end từ CDC (Change Data Capture) đến Dashboard phân tích:

- **CDC Thời gian thực**: PostgreSQL → Debezium → Kafka → Bronze (Streaming)
- **ETL Batch**: Bronze → Silver → Gold (Airflow mỗi 5 phút)
- **Huấn luyện ML**: RandomForest + LogisticRegression (Airflow hàng ngày 2 giờ sáng)
- **Phân tích**: Trino + Metabase Dashboard
- **Chatbot AI**: Streamlit + LangChain + Gemini (tiếng Việt)

## 📚 Tài liệu

- **[Setup Guide](docs/SETUP_GUIDE.md)** - Hướng dẫn cài đặt chi tiết cho người mới
- **[Chatbot Guide](docs/CHATBOT_GUIDE.md)** - Hướng dẫn sử dụng Fraud Chatbot
- **[Chatbot Architecture](docs/CHATBOT_ARCHITECTURE.md)** - Kiến trúc modular của chatbot
- **[Implementation Summary](docs/IMPLEMENTATION_SUMMARY.md)** - Tổng hợp các thay đổi
- **[Changelog](docs/CHANGELOG.md)** - Lịch sử thay đổi dự án

## 🛠️ Công nghệ sử dụng

| Thành phần        | Công nghệ            | Cổng       | Mô tả                             |
| ----------------- | -------------------- | ---------- | --------------------------------- |
| **Cơ sở dữ liệu** | PostgreSQL 14        | 5432       | OLTP database với CDC enabled     |
| **CDC**           | Debezium 2.5         | 8083       | Change Data Capture               |
| **Streaming**     | Apache Kafka         | 9092       | Message broker                    |
| **Xử lý**         | Spark 3.4.1          | 8080       | Xử lý stream & batch              |
| **Lưu trữ**       | Delta Lake + MinIO   | 9000, 9001 | ACID lakehouse                    |
| **Metastore**     | Hive Metastore 3.1.3 | 9083       | Cache metadata (tùy chọn)         |
| **Truy vấn**      | Trino                | 8085       | Công cụ SQL phân tán              |
| **Điều phối**     | Airflow 2.8.0        | 8081       | Lập lịch workflow                 |
| **Theo dõi ML**   | MLflow 2.8.0         | 5001       | Theo dõi mô hình                  |
| **Trực quan hóa** | Metabase             | 3000       | Dashboard BI                      |
| **API**           | FastAPI              | 8000       | Dự đoán thời gian thực (tùy chọn) |
| **Chatbot**       | Streamlit + Gemini   | 8501       | Chat với database bằng tiếng Việt |

## 📋 Yêu cầu hệ thống

**Phần cứng:**

- CPU: 6 cores minimum (khuyến nghị 8+)
- RAM: 10GB minimum (khuyến nghị 16GB)
- Disk: 30GB free space

**Phần mềm:**

- Docker Desktop 4.0+ (Windows/Mac) hoặc Docker Engine 20.10+ (Linux)
- Docker Compose 2.0+
- PowerShell 5.1+ (Windows) hoặc Bash (Linux/Mac)

**Cấu hình Docker (Windows WSL2):**

Tạo file `C:\Users\<YourUsername>\.wslconfig`:

```ini
[wsl2]
memory=10GB
processors=6
swap=4GB
```

Sau đó restart WSL2:

```powershell
wsl --shutdown
```

## 🚀 Hướng dẫn chạy

### 0. Cấu hình Gemini API (Tùy chọn - Cho Chatbot)

Nếu bạn muốn sử dụng Chatbot, cần cấu hình Gemini API key (FREE):

**Bước 1: Lấy API Key**

1. Truy cập: https://aistudio.google.com/app/apikey
2. Đăng nhập Google
3. Click **"Create API Key"**
4. Copy API key (dạng: `AIzaSy...`)

**Bước 2: Tạo file `.env`**

```bash
# Copy file mẫu
cp .env.example .env

# Sửa file .env
notepad .env  # Windows
# hoặc
nano .env     # Linux/Mac
```

**Bước 3: Dán API key vào `.env`**

```bash
GOOGLE_API_KEY=AIzaSyXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
```

**Lưu ý:** Nếu không dùng Chatbot, có thể bỏ qua bước này.

---

### 1. Tải mã nguồn

```bash
git clone https://github.com/bin-bard/real-time-fraud-detection-lakehouse.git
cd real-time-fraud-detection-lakehouse
```

### 2. Khởi động hệ thống

```bash
docker compose up -d --build
```

**⏳ Thời gian khởi động:** ~5-10 phút (tải images + khởi tạo services)

### 3. Tải dữ liệu và quản lý Data Producer

#### 📌 **Data Producer có 2 chế độ hoạt động:**

**🔹 IDLE MODE** (Mặc định - `MODE=idle`):

- Container chỉ sống, **KHÔNG tự động** load data
- Bạn phải chạy thủ công qua `docker exec`
- Dùng cho: Bulk load ban đầu, kiểm soát hoàn toàn

**🔹 AUTO-STREAM MODE** (Bỏ `MODE=idle`):

- Container **tự động streaming** khi start/restart
- Dùng cho: Sau khi đã bulk load xong, muốn stream liên tục

---

#### **A. Bulk Load Ban Đầu (Khuyến nghị - IDLE MODE)**

**Bước 1: Đảm bảo IDLE MODE** (file `docker-compose.yml`):

```yaml
data-producer:
  environment:
    MODE: idle # ← Để IDLE mode
```

**Bước 2: Bulk load 50K giao dịch:**

```bash
# Tải 50K giao dịch (~250 giao dịch gian lận)
docker exec data-producer python producer.py --bulk-load 50000
```

**Kết quả:**

- ✅ ~50K bản ghi trong 2-3 phút
- ✅ ~250 giao dịch gian lận (tỷ lệ 0.5%)
- ✅ Đủ dữ liệu cho huấn luyện ML ngay
- ✅ Checkpoint được lưu, không trùng lặp khi chạy lại

---

#### **B. Chuyển sang AUTO-STREAM MODE (Streaming liên tục)**

**Sau khi bulk load xong**, nếu muốn container **tự động streaming** khi stop/start:

**Bước 1: Sửa `docker-compose.yml`:**

```yaml
data-producer:
  environment:
    # MODE: idle  # ← Comment hoặc xóa dòng này
```

**Bước 2: Restart container:**

```bash
docker compose up -d data-producer
```

**Bước 3: Test auto-streaming:**

```bash
# Stop
docker stop data-producer

# Start → Tự động streaming
docker start data-producer

# Hoặc restart trực tiếp
docker restart data-producer
```

**Kết quả:**

- ✅ Container tự động chạy streaming mode
- ✅ Dữ liệu được load từ từ theo thời gian thực (TIME_SCALING_FACTOR = 0.001)
- ✅ Tiếp tục từ checkpoint, không trùng lặp

---

#### **C. Chạy Streaming thủ công (IDLE MODE)**

Nếu vẫn giữ `MODE=idle`, muốn streaming thủ công:

```bash
docker exec -it data-producer python producer.py
```

**Dừng streaming:** Nhấn `Ctrl+C`

---

#### **📋 Tóm tắt workflow:**

| Mục đích                    | Cách làm                                           |
| --------------------------- | -------------------------------------------------- |
| **Bulk load lần đầu**       | `MODE=idle` + `docker exec ... --bulk-load 50000`  |
| **Auto-stream khi restart** | Xóa `MODE=idle` + `docker restart data-producer`   |
| **Streaming thủ công**      | `MODE=idle` + `docker exec ... python producer.py` |
| **Reset checkpoint**        | `docker compose down -v` (xóa volumes)             |

### 4. Kiểm tra hệ thống

#### Kiểm tra services đang chạy

```bash
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

**Kết quả mong đợi:** 15+ containers với trạng thái `Up`

#### Kiểm tra Bronze streaming

```bash
docker logs bronze-streaming --tail 20
```

**Kết quả mong đợi:**

```
Batch 5 processing started
Writing 142 records to Bronze layer...
✅ Batch 5 written successfully
```

#### Kiểm tra Airflow DAG

- Truy cập: http://localhost:8081 (`admin` / `admin`)
- DAG: `lakehouse_pipeline_taskflow` (chạy mỗi 5 phút)
- Kiểm tra: Các task Silver/Gold chạy thành công

#### Kiểm tra dữ liệu trong MinIO

- Truy cập: http://localhost:9001 (`minio` / `minio123`)
- Bucket: `lakehouse`
- Kiểm tra các thư mục: `bronze/`, `silver/`, `gold/`

#### Truy vấn dữ liệu qua Trino

```bash
docker exec -it trino trino --server localhost:8081
```

```sql
-- Kiểm tra dữ liệu tồn tại
SELECT COUNT(*) FROM delta.bronze.transactions;
SELECT COUNT(*) FROM delta.silver.transactions;
SELECT COUNT(*) FROM delta.gold.fact_transactions;

-- Dữ liệu mẫu
SELECT * FROM delta.gold.fact_transactions LIMIT 5;

-- Phân bố gian lận
SELECT is_fraud, COUNT(*) as count
FROM delta.silver.transactions
GROUP BY is_fraud;

quit;
```

**⚠️ QUAN TRỌNG:** Truy vấn dữ liệu phải dùng catalog **`delta`** (KHÔNG dùng `hive`):

- ✅ `delta.bronze.*`, `delta.silver.*`, `delta.gold.*`
- ❌ `hive.*` (chỉ liệt kê bảng, không truy vấn được định dạng Delta)

## 🔑 Truy cập các dịch vụ

| Dịch vụ             | URL                   | Tên đăng nhập / Mật khẩu | Ghi chú                           |
| ------------------- | --------------------- | ------------------------ | --------------------------------- |
| **Airflow**         | http://localhost:8081 | `admin` / `admin`        | Điều phối workflow                |
| **Spark Master UI** | http://localhost:8080 | -                        | Giám sát các job Spark            |
| **MinIO Console**   | http://localhost:9001 | `minio` / `minio123`     | Lưu trữ Data Lake                 |
| **MLflow UI**       | http://localhost:5001 | -                        | Theo dõi mô hình ML               |
| **Kafka UI**        | http://localhost:9002 | -                        | Topics, messages, consumer groups |
| **Trino UI**        | http://localhost:8085 | -                        | Giám sát công cụ truy vấn         |
| **Metabase**        | http://localhost:3000 | (tạo admin lần đầu)      | Dashboard BI                      |
| **PostgreSQL**      | localhost:5432        | `postgres` / `postgres`  | Cơ sở dữ liệu nguồn               |
| **FastAPI**         | http://localhost:8000 | -                        | API dự đoán gian lận real-time    |
| **Chatbot**         | http://localhost:8501 | -                        | Chat với database (Gemini AI)     |

## 📊 Kiến trúc hệ thống

### Kiến trúc Medallion (Kết hợp: Streaming + Batch)

```
PostgreSQL (Nguồn)
    ↓ Debezium CDC
Kafka (postgres.public.transactions)
    ↓ Bronze Streaming (Liên tục, ~195% CPU)
Bronze Delta Lake (s3a://lakehouse/bronze/)
    ↓ Silver Batch (Mỗi 5 phút qua Airflow)
Silver Delta Lake (s3a://lakehouse/silver/)
    ↓ Gold Batch (Mỗi 5 phút qua Airflow)
Gold Delta Lake (s3a://lakehouse/gold/) - 5 bảng
    ↓
Trino Delta Catalog (Truy vấn dữ liệu)
    ↓
Metabase/DBeaver (Phân tích)
```

**Các lớp dữ liệu:**

1. **Bronze** - Dữ liệu CDC thô (streaming thời gian thực)
2. **Silver** - Làm sạch + Kỹ thuật đặc trưng (batch mỗi 5 phút)
3. **Gold** - Lược đồ sao (Star Schema): 4 chiều + 1 bảng sự kiện (batch mỗi 5 phút)

**Các bảng lớp Gold:**

- `dim_customer` - Chiều khách hàng
- `dim_merchant` - Chiều cửa hàng
- `dim_time` - Chiều thời gian
- `dim_location` - Chiều địa điểm
- `fact_transactions` - Sự kiện giao dịch (25K+ bản ghi)

## 🤖 Huấn luyện ML

### Huấn luyện tự động (Airflow)

- **Lịch trình:** Hàng ngày lúc 2 giờ sáng
- **DAG:** `model_retraining_taskflow`
- **Mô hình:** RandomForest + LogisticRegression
- **Chỉ số:** Độ chính xác, Precision, Recall, F1, AUC

### Kích hoạt thủ công

Airflow UI → `model_retraining_taskflow` → ▶️ Trigger DAG

### Quản lý tài nguyên

**Trước khi chạy huấn luyện ML:**

```powershell
# Giải phóng ~2GB RAM + 1-2 CPU cores
.\scripts\prepare-ml-training.ps1
```

**Sau khi huấn luyện xong:**

```powershell
# Khôi phục các dịch vụ
.\scripts\restore-services.ps1
```

### Kiểm tra mô hình

- Truy cập: http://localhost:5001
- Thí nghiệm: `fraud_detection_production`
- Kiểm tra các lần chạy: RandomForest, LogisticRegression

### Câu hỏi thường gặp về mẫu huấn luyện

**Hỏi: Tại sao chỉ có ~15-20 mẫu huấn luyện?**

**Đáp:** Đây là hành vi ĐÚNG với phát hiện gian lận thực tế!

| Chỉ số                  | Giá trị      | Giải thích                         |
| ----------------------- | ------------ | ---------------------------------- |
| Tổng bản ghi (Silver)   | ~4,200       | Sau vài phút streaming             |
| Giao dịch gian lận      | ~10 (0.24%)  | Tỷ lệ gian lận thực tế 0.5%        |
| Sau cân bằng lớp        | 10 + 10 = 20 | Giảm mẫu lớp đa số xuống tỷ lệ 1:1 |
| Chia train/test (80/20) | 16 + 4       | Tập dữ liệu cuối cùng              |

**Giải pháp:** Tải hàng loạt 50K bản ghi → ~250 mẫu gian lận → huấn luyện tốt hơn

```bash
docker exec data-producer python producer.py --bulk-load 50000
```

## 🔮 API Dự đoán Gian lận (FastAPI)

### Giới thiệu

FastAPI service cung cấp endpoint để dự đoán gian lận real-time sử dụng model từ MLflow.

**Tính năng:**

- ✅ Tự động load model từ MLflow Model Registry
- ✅ Fallback sang rule-based nếu model chưa có
- ✅ Batch prediction cho nhiều giao dịch
- ✅ Reload model sau khi training mới
- ✅ Health check và model info

### Sử dụng API

**1. Kiểm tra trạng thái:**

```bash
curl http://localhost:8000/health
```

**2. Thông tin model:**

```bash
curl http://localhost:8000/model/info
```

**3. Dự đoán đơn lẻ:**

```bash
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{
    "amt": 850.50,
    "log_amount": 6.75,
    "amount_bin": 3,
    "is_zero_amount": 0,
    "is_high_amount": 0,
    "distance_km": 120.5,
    "is_distant_transaction": 1,
    "age": 35,
    "gender_encoded": 1,
    "hour": 23,
    "day_of_week": 6,
    "is_weekend": 1,
    "is_late_night": 1,
    "hour_sin": -0.5,
    "hour_cos": 0.866,
    "trans_num": "T123456",
    "merchant": "fraud_Johnson-Stokes",
    "category": "gas_transport"
  }'
```

**Response:**

```json
{
  "trans_num": "T123456",
  "is_fraud_predicted": 1,
  "fraud_probability": 0.8523,
  "risk_level": "HIGH",
  "model_version": "mlflow_abc123"
}
```

**4. Reload model sau khi training:**

```bash
curl -X POST http://localhost:8000/model/reload
```

### Tích hợp vào Pipeline

**Use Cases (Ví dụ tích hợp - chưa implement sẵn):**

```python
# 1. Alert System (Tự implement)
import requests
import smtplib

def check_and_alert(transaction_features):
    # Gọi API prediction
    response = requests.post(
        "http://fraud-detection-api:8000/predict",
        json=transaction_features
    )
    result = response.json()

    # Gửi cảnh báo nếu HIGH risk
    if result["risk_level"] == "HIGH":
        send_email_alert(
            subject=f"⚠️ High Risk Transaction: {result['trans_num']}",
            body=f"Fraud Probability: {result['fraud_probability']:.2%}"
        )
        # Hoặc gửi Slack notification
        send_slack_alert(result)

# 2. Batch processing qua Spark
def predict_batch_spark(df):
    """Thêm predictions vào Silver layer"""
    from pyspark.sql.functions import udf
    from pyspark.sql.types import StructType, DoubleType, StringType

    @udf(returnType=StructType([...]))
    def predict_udf(features):
        response = requests.post(
            "http://fraud-detection-api:8000/predict",
            json=features
        )
        return response.json()

    return df.withColumn("prediction", predict_udf(...))
```

**⚠️ Lưu ý:** Alert System (email/Slack) là **use case đề xuất**, CHƯA được implement sẵn trong dự án. Bạn cần tự tích hợp dựa vào FastAPI response.

## 📊 SQL Views cho Analytics

### Tạo Views trong Trino

File `sql/gold_layer_views_delta.sql` chứa 9 analytical views để:

- Metabase query dễ hơn (không cần JOIN phức tạp)
- Dashboard real-time metrics
- Chatbot query natural language

**Cách tạo views:**

```bash
# 1. Connect vào Trino
docker exec -it trino trino --server localhost:8081

# 2. Copy-paste từng CREATE VIEW statement từ file sql/gold_layer_views_delta.sql
# Hoặc chạy toàn bộ file (nếu Trino hỗ trợ)
```

**9 Views được tạo:**

1. **`daily_summary`** - Metrics tổng hợp theo ngày

   ```sql
   SELECT * FROM delta.gold.daily_summary
   WHERE report_date >= CURRENT_DATE - INTERVAL '7' DAY;
   ```

2. **`hourly_summary`** - Phân tích patterns theo giờ

   ```sql
   SELECT hour, fraud_rate FROM delta.gold.hourly_summary
   WHERE day = DAY(CURRENT_DATE)
   ORDER BY hour;
   ```

3. **`state_summary`** - Top states có fraud rate cao

   ```sql
   SELECT * FROM delta.gold.state_summary
   ORDER BY fraud_rate DESC LIMIT 10;
   ```

4. **`category_summary`** - Category nào rủi ro nhất

   ```sql
   SELECT * FROM delta.gold.category_summary
   ORDER BY fraud_rate DESC;
   ```

5. **`amount_summary`** - Fraud rate theo khoảng tiền

6. **`latest_metrics`** - Real-time metrics cho monitoring

   ```sql
   SELECT * FROM delta.gold.latest_metrics;
   -- Có alert_level: HIGH/MEDIUM/LOW
   ```

7. **`fraud_patterns`** - Top fraud patterns

8. **`merchant_analysis`** - Merchants nguy hiểm nhất

9. **`time_period_analysis`** - Fraud rate theo Morning/Afternoon/Evening/Night

**Sử dụng trong Metabase:**

Sau khi tạo views, query đơn giản hơn:

```sql
-- Thay vì JOIN phức tạp:
-- SELECT ... FROM fact_transactions f
-- JOIN dim_customer c ON f.customer_key = c.customer_key
-- JOIN dim_merchant m ON ...

-- Chỉ cần:
SELECT * FROM delta.gold.daily_summary;
SELECT * FROM delta.gold.merchant_analysis;
```

## 🤖 Chatbot - Chat với Database bằng Tiếng Việt

### Giới thiệu

Chatbot sử dụng **Gemini AI** + **LangChain** để chat với database bằng ngôn ngữ tự nhiên.

**Tính năng:**

- ✅ Chat bằng tiếng Việt hoặc tiếng Anh
- ✅ Tự động sinh SQL query từ câu hỏi
- ✅ Lưu lịch sử chat vào PostgreSQL
- ✅ Quản lý nhiều sessions
- ✅ Hiển thị SQL query được sinh ra
- ✅ FREE tier (Gemini API miễn phí)

### Truy cập Chatbot

```
http://localhost:8501
```

### Câu hỏi mẫu

**Tiếng Việt:**

- "Có bao nhiêu giao dịch gian lận hôm nay?"
- "Top 5 bang có tỷ lệ gian lận cao nhất?"
- "Hiển thị fraud rate theo từng giờ trong ngày"
- "Merchant nào nguy hiểm nhất?"
- "Tổng số tiền bị gian lận tuần này?"
- "Phân tích fraud patterns theo khoảng tiền"
- "Category nào rủi ro nhất?"
- "Danh sách 10 giao dịch gian lận gần đây"

**Tiếng Anh:**

- "How many fraud transactions today?"
- "Which states have highest fraud rate?"
- "Show fraud rate by hour"
- "Top 10 risky merchants"
- "Total fraud amount this week"
- "Fraud patterns by amount range"

### Quản lý Chat History

**Tính năng lưu trữ:**

- Mỗi session được lưu vào PostgreSQL
- Có thể load lại conversations cũ
- Xóa sessions không cần thiết
- Theo dõi số lượng messages mỗi session

**Database schema:**

```sql
-- Bảng chat_history tự động được tạo
CREATE TABLE chat_history (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(100),
    role VARCHAR(20),  -- 'user' or 'assistant'
    message TEXT,
    sql_query TEXT,    -- SQL được sinh ra
    created_at TIMESTAMP
);
```

**Load lại conversation:**

1. Mở Chatbot sidebar
2. Chọn session từ "Sessions gần đây"
3. Tất cả messages sẽ được load

### Troubleshooting

**Lỗi: "GOOGLE_API_KEY chưa được cấu hình"**

```bash
# 1. Kiểm tra file .env tồn tại
ls .env

# 2. Kiểm tra nội dung
cat .env

# 3. Đảm bảo có dòng:
GOOGLE_API_KEY=AIzaSy...

# 4. Restart chatbot container
docker compose restart fraud-chatbot
```

**Lỗi: "Cannot connect to Trino"**

```bash
# Kiểm tra Trino đang chạy
docker ps | grep trino

# Test connection
docker exec fraud-chatbot python -c "
from sqlalchemy import create_engine
engine = create_engine('trino://trino:8081/delta/gold')
print(engine.table_names())
"
```

**Chatbot response chậm?**

- Gemini API FREE tier có rate limit
- Model `gemini-2.0-flash-exp` là nhanh nhất
- Có thể đổi sang `gemini-1.5-flash` trong `chatbot.py`

## 🔧 Kết nối Metabase

### Cấu hình cơ sở dữ liệu

```yaml
Loại cơ sở dữ liệu: Trino
Tên hiển thị: Fraud Detection Lakehouse

Kết nối:
  Host: trino # Nếu Metabase chạy trong Docker
  # Host: localhost   # Nếu Metabase chạy ngoài Docker
  Port: 8081 # Cổng nội bộ (8085 cho bên ngoài)
  Catalog: delta # ⚠️ QUAN TRỌNG: Dùng delta, không phải hive
  Database: gold # Hoặc 'silver'/'bronze'

Xác thực:
  Username: (để trống)
  Password: (để trống)
```

### Truy vấn mẫu

```sql
-- Tỷ lệ gian lận theo danh mục
SELECT
    transaction_category,
    COUNT(*) as total_transactions,
    SUM(CASE WHEN is_fraud = 1 THEN 1 ELSE 0 END) as fraud_count,
    ROUND(100.0 * SUM(CASE WHEN is_fraud = 1 THEN 1 ELSE 0 END) / COUNT(*), 2) as fraud_rate
FROM delta.gold.fact_transactions
GROUP BY transaction_category
ORDER BY fraud_rate DESC

-- Top 10 cửa hàng rủi ro cao
SELECT
    merchant_name,
    merchant_category,
    COUNT(*) as total_transactions,
    SUM(CASE WHEN is_fraud = 1 THEN 1 ELSE 0 END) as fraud_count
FROM delta.gold.fact_transactions
GROUP BY merchant_name, merchant_category
HAVING COUNT(*) > 10
ORDER BY fraud_count DESC
LIMIT 10
```

## 🔧 Kết nối DBeaver/SQL Client

**JDBC URL:**

```
jdbc:trino://localhost:8085/delta
```

**Cài đặt kết nối:**

- Host: `localhost`
- Cổng: `8085`
- Database/Catalog: `delta`
- Schema: `gold` (hoặc `silver`, `bronze`)
- Tên đăng nhập: `trino` (hoặc bất kỳ)
- Mật khẩu: (để trống)

## 🐛 Xử lý sự cố

### FastAPI không kết nối MLflow

```bash
# 1. Kiểm tra MLflow có chạy
docker logs mlflow --tail 20

# 2. Kiểm tra FastAPI logs
docker logs fraud-detection-api --tail 50

# 3. Test API
curl http://localhost:8000/health

# 4. Reload model sau khi training xong
curl -X POST http://localhost:8000/model/reload
```

### Sử dụng CPU cao (>500%)

**Bình thường:**

- `bronze-streaming`: ~195% CPU (liên tục)
- `spark-master`: ~50-100% CPU khi chạy job
- `airflow-*`: ~10-30% CPU

**Nếu >600%:** Khởi động lại dịch vụ

```bash
docker compose restart bronze-streaming spark-master spark-worker
```

### Không có dữ liệu trong Silver/Gold

```bash
# 1. Kiểm tra Bronze có dữ liệu
docker exec trino trino --server localhost:8081 --execute "SELECT COUNT(*) FROM delta.bronze.transactions"

# 2. Kiểm tra Airflow DAG đang chạy
# Airflow UI: http://localhost:8081 → lakehouse_pipeline_taskflow

# 3. Kiểm tra logs
docker logs airflow-scheduler --tail 50
```

### MLflow trống (không có mô hình)

```bash
# 1. Kiểm tra Silver có đủ dữ liệu (cần ít nhất 1000 bản ghi với mẫu gian lận)
docker exec trino trino --server localhost:8081 --execute "SELECT is_fraud, COUNT(*) FROM delta.silver.transactions GROUP BY is_fraud"

# 2. Kích hoạt DAG huấn luyện
# Airflow UI → model_retraining_taskflow → Trigger DAG

# 3. Kiểm tra logs
# Airflow UI → model_retraining_taskflow → train_ml_models → Logs
```

### Khởi động lại toàn bộ hệ thống

```bash
# ⚠️ Cảnh báo: Xóa toàn bộ dữ liệu!
docker compose down -v
docker compose up -d --build
```

## 📖 Tài liệu

- **[PROJECT_SPECIFICATION.md](docs/PROJECT_SPECIFICATION.md)** - Đặc tả chi tiết kiến trúc, luồng dữ liệu, yêu cầu
- **[CHANGELOG.md](docs/CHANGELOG.md)** - Lịch sử cập nhật, lỗi đã sửa, câu hỏi thường gặp

## 📝 Giấy phép

**Giấy phép MIT (MIT License)**

Copyright (c) 2025 Nhóm 6 - GVHD: ThS. Phan Thị Thể

Giấy phép này cho phép bất kỳ ai có được bản sao của phần mềm và tài liệu liên quan ("Phần mềm") được phép sử dụng Phần mềm mà không bị hạn chế, bao gồm nhưng không giới hạn quyền sử dụng, sao chép, sửa đổi, hợp nhất, xuất bản, phân phối, cấp phép con và/hoặc bán các bản sao của Phần mềm, với các điều kiện sau:

Thông báo bản quyền trên và thông báo giấy phép này phải được bao gồm trong tất cả các bản sao hoặc phần quan trọng của Phần mềm.

PHẦN MỀM ĐƯỢC CUNG CẤP "NGUYÊN TRẠNG", KHÔNG CÓ BẢO HÀNH DƯỚI BẤT KỲ HÌNH THỨC NÀO, RÕ RÀNG HOẶC NGỤ Ý, BAO GỒM NHƯNG KHÔNG GIỚI HẠN BẢO HÀNH VỀ KHẢ NĂNG THƯƠNG MẠI, PHÙ HỢP CHO MỘT MỤC ĐÍCH CỤ THỂ VÀ KHÔNG VI PHẠM. TRONG BẤT KỲ TRƯỜNG HỢP NÀO, TÁC GIẢ HOẶC CHỦ SỞ HỮU BẢN QUYỀN KHÔNG CHỊU TRÁCH NHIỆM VỀ BẤT KỲ YÊU CẦU, THIỆT HẠI HOẶC TRÁCH NHIỆM PHÁP LÝ NÀO.

## 👥 Thành viên nhóm

- Nguyễn Thanh Tài - 22133049
- Võ Triệu Phúc - 22133043
