# ĐẶC TẢ YÊU CẦU DỰ ÁN (PROJECT SPECIFICATION)

**Tên đề tài:** Xây dựng hệ thống Data Lakehouse để phát hiện và xác minh gian lận tài chính trong thời gian thực.
**Nhóm thực hiện:** Nhóm 6
**Thành viên:**

1. Nguyễn Thanh Tài - 22133049
2. Võ Triệu Phúc - 22133043
   **GVHD:** ThS. Phan Thị Thể
   **Phiên bản:** 5.0

---

## 1. TỔNG QUAN DỰ ÁN (PROJECT OVERVIEW)

### 1.1. Mục tiêu cốt lõi

Dự án xây dựng một **Modern Data Platform (Nền tảng dữ liệu hiện đại)** giải quyết bài toán phát hiện gian lận thẻ tín dụng với các đặc điểm:

1. **Real-time Processing:** Xử lý luồng giao dịch liên tục, phát hiện gian lận ngay khi sự kiện xảy ra.
2. **Lakehouse Architecture:** Sử dụng Delta Lake để đảm bảo tính toàn vẹn (ACID) và truy vết lịch sử (Time Travel).
3. **Real-time Inference:** Tích hợp mô hình AI qua API độc lập để chấm điểm gian lận tức thời.
4. **Interactive Verification:** Cung cấp Chatbot và Dashboard giúp chuyên viên điều tra truy vấn dữ liệu theo ngôn ngữ tự nhiên.

### 1.2. Phạm vi dữ liệu

Hệ thống xử lý luồng dữ liệu giả lập từ 01/01/2019 đến 31/12/2020. Dữ liệu được "phát lại" (replayed) để mô phỏng môi trường thời gian thực.

---

## 2. DỮ LIỆU SỬ DỤNG (DATASET)

**Tên bộ dữ liệu:** Credit Card Transactions Fraud Detection Dataset (Sparkov Data Generation).
**Nguồn:** [Kaggle - Kartik Shenoy](https://www.kaggle.com/datasets/kartik2112/fraud-detection)

### Schema chi tiết (Dữ liệu đầu vào):

_Lưu ý: Dữ liệu CSV gốc có thể có cột index (số thứ tự) không tên ở đầu, hệ thống sẽ bỏ qua cột này._

| STT | Tên cột                 | Kiểu dữ liệu | Ý nghĩa nghiệp vụ                               |
| :-- | :---------------------- | :----------- | :---------------------------------------------- |
| 1   | `trans_date_trans_time` | DateTime     | Thời gian giao dịch.                            |
| 2   | `cc_num`                | Long         | Số thẻ tín dụng (ID khách hàng).                |
| 3   | `merchant`              | String       | Tên đơn vị bán hàng (VD: fraud_Rippin).         |
| 4   | `category`              | String       | Danh mục (VD: grocery_pos).                     |
| 5   | `amt`                   | Double       | Số tiền giao dịch.                              |
| 6   | `first`                 | String       | Tên đệm.                                        |
| 7   | `last`                  | String       | Họ.                                             |
| 8   | `gender`                | String       | Giới tính (M/F).                                |
| 9   | `street`                | String       | Địa chỉ đường.                                  |
| 10  | `city`                  | String       | Thành phố.                                      |
| 11  | `state`                 | String       | Bang.                                           |
| 12  | `zip`                   | Integer      | Mã bưu chính.                                   |
| 13  | `lat`                   | Double       | **Vị trí chủ thẻ (Latitude) - Quan trọng.**     |
| 14  | `long`                  | Double       | **Vị trí chủ thẻ (Longitude) - Quan trọng.**    |
| 15  | `city_pop`              | Integer      | Dân số thành phố.                               |
| 16  | `job`                   | String       | Nghề nghiệp.                                    |
| 17  | `dob`                   | Date         | Ngày sinh (Dùng tính tuổi).                     |
| 18  | `trans_num`             | String       | Mã giao dịch.                                   |
| 19  | `unix_time`             | Long         | Thời gian dạng Unix Timestamp (VD: 1325376018). |
| 20  | `merch_lat`             | Double       | **Vị trí cửa hàng (Latitude) - Quan trọng.**    |
| 21  | `merch_long`            | Double       | **Vị trí cửa hàng (Longitude) - Quan trọng.**   |
| 22  | `is_fraud`              | Integer      | Nhãn thực tế (0: Sạch, 1: Gian lận).            |

---

## 3. KIẾN TRÚC HỆ THỐNG (SYSTEM ARCHITECTURE)

Hệ thống được chia thành các tầng (Layers) rõ ràng theo mô hình Lakehouse:

### 3.1. Layer 1: Ingestion (Thu thập)

- **PostgreSQL:** Đóng vai trò là Database nguồn (OLTP).
- **Debezium:** Công cụ CDC bắt các thay đổi `INSERT` từ Postgres và đẩy vào Kafka.
- **Apache Kafka:** Hàng đợi thông điệp trung gian.

### 3.2. Layer 2: Storage (Lưu trữ - Lakehouse)

- **MinIO:** Object Storage (S3 Compatible).
- **Delta Lake:** Định dạng lưu trữ bảng (Bronze, Silver, Gold).
- **Hive Metastore:** Quản lý metadata trung tâm.

### 3.3. Layer 3: Processing (Xử lý Stream)

- **Apache Spark (Structured Streaming):** Engine xử lý chính, chạy liên tục 24/7 để chuyển đổi dữ liệu từ Kafka -> Bronze -> Silver -> Gold.

#### 3.3.1. Chiến lược xử lý dữ liệu null

Hệ thống áp dụng chiến lược xử lý null khác nhau cho từng layer theo nguyên tắc Lakehouse:

**Bronze Layer (Raw Data):**

- Giữ nguyên tất cả dữ liệu thô từ CDC (Debezium).
- Chỉ filter tombstone/delete messages (after = null).
- Không fillna hay dropna để đảm bảo tính toàn vẹn của raw data.

**Silver Layer (Curated Data):**

_Data Quality Checks:_

1. **Loại bỏ records không thể trace:**

   - `trans_num` (mã giao dịch): NULL → DROP record
   - `cc_num` (ID khách hàng): NULL → DROP record
   - `trans_timestamp` (partition key): NULL → DROP record
   - _Lý do:_ Không thể trace/analyze giao dịch không có ID.

2. **Fill null cho business-critical fields:**

   - `amt` (số tiền): NULL → Fill `0` (giao dịch không hợp lệ nhưng vẫn ghi nhận)
   - `is_fraud` (label): NULL → Fill `0` (assume normal transaction)

3. **Giữ null có ý nghĩa (semantic null):**
   - `lat`, `long`, `merch_lat`, `merch_long`: Giữ NULL → Xử lý trong feature engineering
   - _Lý do:_ NULL = "không có thông tin vị trí" ≠ tọa độ 0,0 (sai thông tin)

_Feature Engineering với Null-Safe Logic:_

- `distance_km`: NULL khi thiếu tọa độ → Fill `-1` (đánh dấu missing, model học pattern)
- `age`: NULL khi thiếu `dob` → Fill `-1` (unknown age)
- `gender_encoded`: NULL → Fill `0` (assume female as default)
- Time features (`hour`, `day_of_week`): Không có null (trans_timestamp đã validated)
- Amount features: Không có null (amt đã filled 0)

**Gold Layer (Analytics-Ready - Star Schema):**

Gold Layer sử dụng **mô hình Dimensional (Star Schema)** để tối ưu phân tích và truy vấn:

_Dimensional Tables (Chiều):_

1. **dim_customer** - Thông tin khách hàng

   - `customer_key` (PK = cc_num)
   - Demographic: `first_name`, `last_name`, `gender`, `age`, `dob`, `job`
   - Location: `customer_city`, `customer_state`, `customer_zip`, `customer_lat`, `customer_long`
   - `customer_city_population`
   - `last_updated` (metadata)

2. **dim_merchant** - Thông tin cửa hàng

   - `merchant_key` (PK - surrogate key)
   - `merchant` (tên cửa hàng)
   - `merchant_category` (loại hình kinh doanh)
   - `merchant_lat`, `merchant_long` (vị trí)
   - `last_updated` (metadata)

3. **dim_time** - Chi tiết thời gian

   - `time_key` (PK - format: yyyyMMddHH)
   - Date components: `year`, `month`, `day`, `hour`, `minute`
   - Calendar: `day_of_week`, `week_of_year`, `quarter`
   - Labels: `day_name`, `month_name`, `time_period` (Morning/Afternoon/Evening/Night)
   - Flags: `is_weekend`

4. **dim_location** - Chi tiết địa điểm
   - `location_key` (PK - surrogate key)
   - `city`, `state`, `zip`
   - `lat`, `long`
   - `city_pop` (dân số)
   - `last_updated` (metadata)

_Fact Table (Sự kiện):_

5. **fact_transactions** - Bảng trung tâm chứa tất cả giao dịch
   - **Keys:**
     - `transaction_key` (PK = trans_num)
     - `customer_key` (FK → dim_customer)
     - `merchant_key` (FK → dim_merchant)
     - `time_key` (FK → dim_time)
   - **Measures (Metrics):**
     - `transaction_amount` (số tiền)
     - `is_fraud` (nhãn thực tế)
     - `fraud_prediction` (dự đoán từ ML model)
     - `distance_km` (khoảng cách tính toán)
     - `log_amount`, `amount_bin` (amount features)
   - **Degenerate Dimensions:**
     - `transaction_timestamp`, `transaction_category`, `unix_time`
   - **Risk Indicators (Flags):**
     - `is_distant_transaction`, `is_late_night`, `is_zero_amount`, `is_high_amount`
   - **Time Features:**
     - `transaction_hour`, `transaction_day_of_week`, `is_weekend_transaction`
     - Cyclic encoding: `hour_sin`, `hour_cos`
   - **Metadata:**
     - `ingestion_time`, `fact_created_time`

_SQL Views (Tối ưu truy vấn):_

Trino tạo các **materialized views** trên dimensional model:

- `daily_summary` - Metrics tổng hợp theo ngày
- `hourly_summary` - Phân tích patterns theo giờ
- `state_summary` - Phân tích địa lý theo bang
- `category_summary` - Phân tích theo danh mục
- `amount_summary` - Phân tích theo khoảng tiền
- `latest_metrics` - Real-time monitoring metrics
- `fraud_patterns` - Top fraud patterns
- `merchant_analysis` - Phân tích merchants
- `time_period_analysis` - Phân tích theo time period

_Null-Safe Aggregations:_

- Views sử dụng logic: `avg(CASE WHEN distance_km >= 0 THEN distance_km END)` (bỏ qua missing `-1`)
- `sum(amt)`, `count(*)` an toàn vì đã processed ở Silver
- Không có NULL trong metrics quan trọng cho Dashboard/BI

_Lợi ích Star Schema:_

- **Truy vấn nhanh:** Joins đơn giản (fact → dims)
- **Linh hoạt:** Ad-hoc queries cho Chatbot/BI
- **Hiệu quả:** Pre-joined data, optimized cho OLAP
- **Mở rộng:** Dễ thêm dimensions/metrics mới

### 3.4. Layer 4: Inference (Dự đoán AI)

- **FastAPI:** Cung cấp API `/predict`. Nhận thông tin giao dịch từ Spark, trả về kết quả dự đoán gian lận.

### 3.5. Layer 5: Orchestration (Điều phối Batch)

- **Apache Airflow:** Quản lý các tác vụ **định kỳ (Scheduled Tasks)** như huấn luyện mô hình và bảo trì hệ thống.

### 3.6. Layer 6: Query & Consumption (Truy vấn & Sử dụng)

- **Trino (PrestoSQL):** Engine truy vấn SQL phân tán tốc độ cao.
- **Metabase:** Dashboard giám sát.
- **Chatbot (Streamlit + LangChain):** Công cụ xác minh nghiệp vụ.

---

## 4. QUY TRÌNH XỬ LÝ CHI TIẾT (WORKFLOWS)

### 4.1. Luồng xử lý thời gian thực (Real-time Streaming Pipeline)

_Luồng này chạy liên tục 24/7, do Spark Streaming đảm nhận, Airflow không can thiệp._

1. **Phát sinh giao dịch:** Python Producer `INSERT` 1 dòng vào PostgreSQL (Giả lập giao dịch mới).
2. **CDC:** Debezium bắt sự kiện Insert -> Gửi bản tin JSON vào Kafka topic `transactions`.
3. **Spark - Bronze Layer:** Spark đọc từ Kafka, ghi dữ liệu thô vào bảng **Bronze** (Append-only).

   - Filter tombstone messages (Debezium delete events với `after = null`).
   - Giữ nguyên tất cả null values trong data (raw data integrity).
   - Parse Debezium `after` field và partition theo `year/month/day`.

4. **Spark - Silver Layer (Quan trọng):**

   - Đọc từ dòng mới nhất của Bronze.
   - **Data Quality Checks:**
     - Drop records có `trans_num`, `cc_num`, hoặc `trans_timestamp` NULL.
     - Fill `amt = 0` nếu NULL (giao dịch không hợp lệ).
     - Fill `is_fraud = 0` nếu NULL (assume normal).
     - Deduplicate theo `trans_num`.
   - **Feature Engineering:**
     - Tính `distance_km`: Khoảng cách Haversine giữa chủ thẻ và cửa hàng (fill `-1` nếu thiếu tọa độ).
     - Tính `age`: Tuổi của chủ thẻ (fill `-1` nếu thiếu `dob`).
     - Tính time features: `hour`, `day_of_week`, `is_weekend`, cyclic encoding.
     - Tính amount features: `log_amount`, `amount_bin`, risk indicators.
   - **Real-time Inference (Gọi API):** Spark gửi các feature (`amt`, `distance`, `age`...) đến **FastAPI**.
     - _Lưu ý:_ Không gửi cột `is_fraud` (đáp án) cho API.
   - **Lưu kết quả:** Lưu vào bảng **Silver** gồm cả cột `is_fraud` (thực tế từ nguồn - dùng để đối chiếu) và `fraud_prediction` (do API dự đoán - dùng để cảnh báo).

5. **Spark - Gold Layer (Dimensional Model):** Spark tự động tạo/cập nhật các bảng Dimension và Fact theo mô hình Star Schema:
   - **Dimension Tables:** `dim_customer`, `dim_merchant`, `dim_time`, `dim_location`
   - **Fact Table:** `fact_transactions` (chứa tất cả metrics và foreign keys)
   - Mô hình này phục vụ cả Dashboard (Metabase) và Chatbot (ad-hoc queries qua Trino)
   - Trino tạo **SQL Views** trên dimensional model để tối ưu queries thường dùng (daily_summary, state_summary, fraud_patterns...)

### 4.2. Luồng Batch & Bảo trì (Batch Pipeline - Airflow Detail)

_Luồng này chạy định kỳ theo lịch, do **Airflow** kích hoạt._

#### **DAG 01: Automated Model Retraining (Tự động huấn luyện lại mô hình)**

- **Lịch chạy:** 00:00 Hàng ngày.
- **Tasks:**
  1. **Extract:** Spark đọc dữ liệu lịch sử từ bảng **Silver**.
  2. **Train:** Huấn luyện lại mô hình (Random Forest/Logistic Regression).
  3. **Evaluate:** So sánh hiệu quả với mô hình hiện tại.
  4. **Register:** Nếu tốt hơn -> Đăng ký vào MLflow và cập nhật endpoint cho FastAPI.

#### **DAG 02: Lakehouse Maintenance (Bảo trì hệ thống)**

- **Lịch chạy:** 02:00 sáng Chủ Nhật hàng tuần.
- **Tasks:**
  1. **Optimize:** Gộp các file nhỏ (small files) sinh ra do streaming thành file lớn.
  2. **Vacuum:** Xóa vật lý các file dữ liệu cũ không còn dùng đến để giải phóng dung lượng MinIO.
  3. **Refresh Views:** Cập nhật metadata cho Trino views (nếu cần).

### 4.3. Luồng Nghiệp vụ (Business Flow)

1. **Giám sát:** Chuyên viên nhìn Dashboard Metabase (query từ Gold views: `daily_summary`, `latest_metrics`), thấy cảnh báo gian lận tăng cao tại khu vực New York.
2. **Điều tra:** Chuyên viên mở Chatbot Streamlit, nhập câu hỏi: _"Liệt kê 5 giao dịch gian lận có số tiền lớn nhất tại New York trong 30 phút qua"_.
3. **Xử lý:** Chatbot (qua Trino) truy vấn dimensional model (`fact_transactions` JOIN `dim_customer`, `dim_merchant`) -> Trả về danh sách chi tiết.
4. **Quyết định:** Chuyên viên xác minh và thực hiện khóa thẻ trên hệ thống nguồn.

---

## 5. YÊU CẦU CÔNG NGHỆ & MÔI TRƯỜNG

### 5.1. Môi trường phát triển & triển khai

**Hệ điều hành yêu cầu:** Windows 10/11 (64-bit)

**Công cụ bắt buộc:**

- **Docker Desktop for Windows** (phiên bản 4.x trở lên)
  - WSL 2 backend được khuyến nghị
  - Yêu cầu tối thiểu: 8GB RAM, 50GB disk space
- **PowerShell 5.1+** (Đã cài sẵn trên Windows)

**⚠️ Lưu ý quan trọng:**

- Dự án được thiết kế **chỉ cho môi trường Windows + Docker Desktop**.
- **KHÔNG** cần tạo các script Linux (`.sh`) riêng cho host machine.
- Các file `.sh` trong project chỉ chạy **bên trong Docker containers** (Linux-based images), không được thực thi trực tiếp trên Windows host.
- Sử dụng **PowerShell scripts (`.ps1`)** cho tất cả automation tasks trên Windows host.

### 5.2. Kiến trúc triển khai (Docker Compose)

Hệ thống triển khai hoàn toàn trên Docker Compose:

| Thành phần        | Image/Service            | Cổng (Port) | Vai trò                 |
| :---------------- | :----------------------- | :---------- | :---------------------- |
| **Source DB**     | `postgres:14`            | 5432        | Nguồn dữ liệu giả lập.  |
| **CDC**           | `debezium/connect`       | 8083        | Bắt thay đổi dữ liệu.   |
| **Kafka**         | `confluentinc/cp-kafka`  | 9092        | Hàng đợi thông điệp.    |
| **Storage**       | `minio/minio`            | 9000, 9001  | Data Lake (S3).         |
| **Spark**         | `bitnami/spark`          | 7077, 8080  | Xử lý Stream & Batch.   |
| **Query Engine**  | `trinodb/trino`          | 8082        | Truy vấn SQL tương tác. |
| **Orchestration** | `apache/airflow`         | 8081        | Điều phối tác vụ Batch. |
| **MLOps**         | `ghcr.io/mlflow/mlflow`  | 5000        | Quản lý model.          |
| **Visualization** | `metabase/metabase`      | 3000        | Dashboard.              |
| **API**           | `fastapi-app` (Custom)   | 8000        | API dự đoán Real-time.  |
| **Chatbot**       | `streamlit-app` (Custom) | 8501        | Giao diện Chatbot.      |

### 5.3. Cấu trúc thư mục quan trọng

```
real-time-fraud-detection-lakehouse/
├── deployment/              # Scripts tự động chạy trong Docker containers
│   ├── debezium/           # Auto-setup Debezium connector (.sh - runs in container)
│   └── minio/              # Auto-setup MinIO buckets (.sh - runs in container)
├── scripts/                # Windows automation scripts
│   ├── cleanup.ps1         # Cleanup Docker resources (PowerShell)
│   └── wait-for-services.ps1  # Health check utility (PowerShell)
├── database/               # PostgreSQL initialization scripts
├── spark/app/              # PySpark jobs (chạy trong Spark containers)
├── services/               # Custom services (FastAPI, Chatbot, Producer)
└── docker-compose.yml      # Orchestration configuration
```

**Quy tắc phân chia scripts:**

- **PowerShell (`.ps1`)**: Chạy trên Windows host để quản lý Docker (start/stop/cleanup)
- **Bash (`.sh`)**: Chỉ chạy bên trong Linux containers (deployment automation, service initialization)

---

## 6. KẾT QUẢ BÀN GIAO (DELIVERABLES)

1. **Mã nguồn (Source Code):** Full stack trên GitHub, bao gồm scripts khởi tạo và Docker Compose.
2. **Báo cáo (Report):** Tài liệu thuyết minh chi tiết kiến trúc Lakehouse, giải thích thuật toán ML và quy trình Airflow.
3. **Sản phẩm Demo:**
   - Hệ thống chạy mượt mà từ Ingestion -> Dashboard (Real-time).
   - Chatbot trả lời đúng câu hỏi nghiệp vụ.
   - Mô hình AI đưa ra dự đoán cho từng giao dịch.
   - Airflow hiển thị các DAGs chạy thành công.
