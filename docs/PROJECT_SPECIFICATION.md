
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

*Lưu ý: Dữ liệu CSV gốc có thể có cột index (số thứ tự) không tên ở đầu, hệ thống sẽ bỏ qua cột này.*

| STT | Tên cột                 | Kiểu dữ liệu | Ý nghĩa nghiệp vụ                                    |
| :-- | :------------------------ | :-------------- | :------------------------------------------------------- |
| 1   | `trans_date_trans_time` | DateTime        | Thời gian giao dịch.                                   |
| 2   | `cc_num`                | Long            | Số thẻ tín dụng (ID khách hàng).                   |
| 3   | `merchant`              | String          | Tên đơn vị bán hàng (VD: fraud_Rippin).            |
| 4   | `category`              | String          | Danh mục (VD: grocery_pos).                             |
| 5   | `amt`                   | Double          | Số tiền giao dịch.                                    |
| 6   | `first`                 | String          | Tên đệm.                                              |
| 7   | `last`                  | String          | Họ.                                                     |
| 8   | `gender`                | String          | Giới tính (M/F).                                       |
| 9   | `street`                | String          | Địa chỉ đường.                                     |
| 10  | `city`                  | String          | Thành phố.                                             |
| 11  | `state`                 | String          | Bang.                                                    |
| 12  | `zip`                   | Integer         | Mã bưu chính.                                         |
| 13  | `lat`                   | Double          | **Vị trí chủ thẻ (Latitude) - Quan trọng.**   |
| 14  | `long`                  | Double          | **Vị trí chủ thẻ (Longitude) - Quan trọng.**  |
| 15  | `city_pop`              | Integer         | Dân số thành phố.                                    |
| 16  | `job`                   | String          | Nghề nghiệp.                                           |
| 17  | `dob`                   | Date            | Ngày sinh (Dùng tính tuổi).                          |
| 18  | `trans_num`             | String          | Mã giao dịch.                                          |
| 19  | `unix_time`             | Long            | Thời gian dạng Unix Timestamp (VD: 1325376018).        |
| 20  | `merch_lat`             | Double          | **Vị trí cửa hàng (Latitude) - Quan trọng.**  |
| 21  | `merch_long`            | Double          | **Vị trí cửa hàng (Longitude) - Quan trọng.** |
| 22  | `is_fraud`              | Integer         | Nhãn thực tế (0: Sạch, 1: Gian lận).                |

---

## 3. KIẾN TRÚC HỆ THỐNG (SYSTEM ARCHITECTURE)

Hệ thống được chia thành các tầng (Layers) rõ ràng theo mô hình Lakehouse:

### 3.1. Layer 1: Ingestion (Thu thập)

* **PostgreSQL:** Đóng vai trò là Database nguồn (OLTP).
* **Debezium:** Công cụ CDC bắt các thay đổi `INSERT` từ Postgres và đẩy vào Kafka.
* **Apache Kafka:** Hàng đợi thông điệp trung gian.

### 3.2. Layer 2: Storage (Lưu trữ - Lakehouse)

* **MinIO:** Object Storage (S3 Compatible).
* **Delta Lake:** Định dạng lưu trữ bảng (Bronze, Silver, Gold).
* **Hive Metastore:** Quản lý metadata trung tâm.

### 3.3. Layer 3: Processing (Xử lý Stream)

* **Apache Spark (Structured Streaming):** Engine xử lý chính, chạy liên tục 24/7 để chuyển đổi dữ liệu từ Kafka -> Bronze -> Silver -> Gold.

### 3.4. Layer 4: Inference (Dự đoán AI)

* **FastAPI:** Cung cấp API `/predict`. Nhận thông tin giao dịch từ Spark, trả về kết quả dự đoán gian lận.

### 3.5. Layer 5: Orchestration (Điều phối Batch)

* **Apache Airflow:** Quản lý các tác vụ **định kỳ (Scheduled Tasks)** như huấn luyện mô hình và bảo trì hệ thống.

### 3.6. Layer 6: Query & Consumption (Truy vấn & Sử dụng)

* **Trino (PrestoSQL):** Engine truy vấn SQL phân tán tốc độ cao.
* **Metabase:** Dashboard giám sát.
* **Chatbot (Streamlit + LangChain):** Công cụ xác minh nghiệp vụ.

---

## 4. QUY TRÌNH XỬ LÝ CHI TIẾT (WORKFLOWS)

### 4.1. Luồng xử lý thời gian thực (Real-time Streaming Pipeline)

*Luồng này chạy liên tục 24/7, do Spark Streaming đảm nhận, Airflow không can thiệp.*

1. **Phát sinh giao dịch:** Python Producer `INSERT` 1 dòng vào PostgreSQL (Giả lập giao dịch mới).
2. **CDC:** Debezium bắt sự kiện Insert -> Gửi bản tin JSON vào Kafka topic `transactions`.
3. **Spark - Bronze Layer:** Spark đọc từ Kafka, ghi dữ liệu thô vào bảng **Bronze** (Append-only).
4. **Spark - Silver Layer (Quan trọng):**
   * Đọc từ dòng mới nhất của Bronze.
   * **Feature Engineering:**
     * Tính `distance_km`: Khoảng cách Haversine giữa chủ thẻ và cửa hàng.
     * Tính `age`: Tuổi của chủ thẻ.
   * **Real-time Inference (Gọi API):** Spark gửi các feature (`amt`, `distance`, `age`...) đến **FastAPI**.
     * *Lưu ý:* Không gửi cột `is_fraud` (đáp án) cho API.
   * **Lưu kết quả:** Lưu vào bảng **Silver** gồm cả cột `is_fraud` (thực tế từ nguồn - dùng để đối chiếu) và `fraud_prediction` (do API dự đoán - dùng để cảnh báo).
5. **Spark - Gold Layer:** Spark tự động tính toán lại các chỉ số tổng hợp (VD: Số lượng gian lận theo giờ) và cập nhật vào bảng **Gold**.

### 4.2. Luồng Batch & Bảo trì (Batch Pipeline - Airflow Detail)

*Luồng này chạy định kỳ theo lịch, do **Airflow** kích hoạt.*

#### **DAG 01: Automated Model Retraining (Tự động huấn luyện lại mô hình)**

* **Lịch chạy:** 00:00 Hàng ngày.
* **Tasks:**
  1. **Extract:** Spark đọc dữ liệu lịch sử từ bảng **Silver**.
  2. **Train:** Huấn luyện lại mô hình (Random Forest/Logistic Regression).
  3. **Evaluate:** So sánh hiệu quả với mô hình hiện tại.
  4. **Register:** Nếu tốt hơn -> Đăng ký vào MLflow và cập nhật endpoint cho FastAPI.

#### **DAG 02: Lakehouse Maintenance (Bảo trì hệ thống)**

* **Lịch chạy:** 02:00 sáng Chủ Nhật hàng tuần.
* **Tasks:**
  1. **Optimize:** Gộp các file nhỏ (small files) sinh ra do streaming thành file lớn.
  2. **Vacuum:** Xóa vật lý các file dữ liệu cũ không còn dùng đến để giải phóng dung lượng MinIO.

#### **DAG 03: Daily Reporting (Báo cáo ngày)**

* **Lịch chạy:** 23:55 Hàng ngày.
* **Tasks:**
  1. **Aggregate:** Tính toán tổng kết ngày (Doanh thu, Tỉ lệ gian lận).
  2. **Write Gold:** Lưu vào bảng báo cáo tĩnh (Static Report Table) để Dashboard load nhanh hơn.

### 4.3. Luồng Nghiệp vụ (Business Flow)

1. **Giám sát:** Chuyên viên nhìn Dashboard Metabase, thấy cảnh báo gian lận tăng cao tại khu vực New York.
2. **Điều tra:** Chuyên viên mở Chatbot Streamlit, nhập câu hỏi: *"Liệt kê 5 giao dịch gian lận có số tiền lớn nhất tại New York trong 30 phút qua"*.
3. **Xử lý:** Chatbot (qua Trino) truy vấn dữ liệu từ Silver/Gold -> Trả về danh sách chi tiết.
4. **Quyết định:** Chuyên viên xác minh và thực hiện khóa thẻ trên hệ thống nguồn.

---

## 5. YÊU CẦU CÔNG NGHỆ & MÔI TRƯỜNG

Hệ thống triển khai hoàn toàn trên Docker Compose:

| Thành phần            | Image/Service              | Cổng (Port) | Vai trò                     |
| :---------------------- | :------------------------- | :----------- | :--------------------------- |
| **Source DB**     | `postgres:14`            | 5432         | Nguồn dữ liệu giả lập.  |
| **CDC**           | `debezium/connect`       | 8083         | Bắt thay đổi dữ liệu.   |
| **Kafka**         | `confluentinc/cp-kafka`  | 9092         | Hàng đợi thông điệp.   |
| **Storage**       | `minio/minio`            | 9000, 9001   | Data Lake (S3).              |
| **Spark**         | `bitnami/spark`          | 7077, 8080   | Xử lý Stream & Batch.      |
| **Query Engine**  | `trinodb/trino`          | 8082         | Truy vấn SQL tương tác.  |
| **Orchestration** | `apache/airflow`         | 8081         | Điều phối tác vụ Batch. |
| **MLOps**         | `ghcr.io/mlflow/mlflow`  | 5000         | Quản lý model.             |
| **Visualization** | `metabase/metabase`      | 3000         | Dashboard.                   |
| **API**           | `fastapi-app` (Custom)   | 8000         | API dự đoán Real-time.    |
| **Chatbot**       | `streamlit-app` (Custom) | 8501         | Giao diện Chatbot.          |

---

## 6. KẾT QUẢ BÀN GIAO (DELIVERABLES)

1. **Mã nguồn (Source Code):** Full stack trên GitHub, bao gồm scripts khởi tạo và Docker Compose.
2. **Báo cáo (Report):** Tài liệu thuyết minh chi tiết kiến trúc Lakehouse, giải thích thuật toán ML và quy trình Airflow.
3. **Sản phẩm Demo:**
   * Hệ thống chạy mượt mà từ Ingestion -> Dashboard (Real-time).
   * Chatbot trả lời đúng câu hỏi nghiệp vụ.
   * Mô hình AI đưa ra dự đoán cho từng giao dịch.
   * Airflow hiển thị các DAGs chạy thành công.
