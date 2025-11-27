
# ĐẶC TẢ YÊU CẦU DỰ ÁN (PROJECT SPECIFICATION)

**Tên đề tài:** Xây dựng hệ thống Data Lakehouse để phát hiện và xác minh gian lận tài chính trong thời gian thực.
**Nhóm thực hiện:** Nhóm 6
**Thành viên:**

1. Nguyễn Thanh Tài - 22133049
2. Võ Triệu Phúc - 22133043
   **GVHD:** ThS. Phan Thị Thể
   **Phiên bản:** 4.0

---

## 1. TỔNG QUAN DỰ ÁN (PROJECT OVERVIEW)

### 1.1. Mục tiêu cốt lõi

Dự án xây dựng một **Modern Data Platform (Nền tảng dữ liệu hiện đại)** giải quyết bài toán phát hiện gian lận thẻ tín dụng với các đặc điểm:

1. **Real-time Processing:** Xử lý luồng giao dịch liên tục, phát hiện gian lận ngay khi sự kiện xảy ra.
2. **Lakehouse Architecture:** Sử dụng Delta Lake để đảm bảo tính toàn vẹn (ACID) và truy vết lịch sử (Time Travel).
3. **Real-time Inference:** Tích hợp mô hình AI qua API để chấm điểm gian lận tức thời.
4. **Interactive Verification:** Cung cấp Chatbot và Dashboard giúp chuyên viên điều tra truy vấn dữ liệu theo ngôn ngữ tự nhiên.

### 1.2. Phạm vi dữ liệu

Hệ thống xử lý luồng dữ liệu giả lập từ 01/01/2019 đến 31/12/2020. Dữ liệu được "phát lại" (replayed) để mô phỏng môi trường thời gian thực.

---

## 2. DỮ LIỆU SỬ DỤNG (DATASET)

**Tên bộ dữ liệu:** Credit Card Transactions Fraud Detection Dataset (Sparkov Data Generation).
**Nguồn:** [Kaggle - Kartik Shenoy](https://www.kaggle.com/datasets/kartik2112/fraud-detection)

### Schema chi tiết (Dữ liệu đầu vào):

*Lưu ý: Dữ liệu CSV gốc có thể có cột index không tên ở đầu, hệ thống sẽ bỏ qua cột này.*

| STT | Tên cột                 | Kiểu dữ liệu | Ý nghĩa nghiệp vụ                             |
| :-- | :------------------------ | :-------------- | :------------------------------------------------ |
| 1   | `trans_date_trans_time` | DateTime        | Thời gian giao dịch.                            |
| 2   | `cc_num`                | Long            | Số thẻ tín dụng (ID khách hàng).            |
| 3   | `merchant`              | String          | Tên đơn vị bán hàng (VD: fraud_Rippin).     |
| 4   | `category`              | String          | Danh mục (VD: grocery_pos).                      |
| 5   | `amt`                   | Double          | Số tiền giao dịch.                             |
| 6   | `first`                 | String          | Tên đệm.                                       |
| 7   | `last`                  | String          | Họ.                                              |
| 8   | `gender`                | String          | Giới tính (M/F).                                |
| 9   | `street`                | String          | Địa chỉ đường.                              |
| 10  | `city`                  | String          | Thành phố.                                      |
| 11  | `state`                 | String          | Bang.                                             |
| 12  | `zip`                   | Integer         | Mã bưu chính.                                  |
| 13  | `lat`                   | Double          | Vị trí chủ thẻ (Latitude).                    |
| 14  | `long`                  | Double          | Vị trí chủ thẻ (Longitude).                   |
| 15  | `city_pop`              | Integer         | Dân số thành phố.                             |
| 16  | `job`                   | String          | Nghề nghiệp.                                    |
| 17  | `dob`                   | Date            | Ngày sinh.                                       |
| 18  | `trans_num`             | String          | Mã giao dịch.                                   |
| 19  | `unix_time`             | Long            | Thời gian dạng Unix Timestamp (VD: 1325376018). |
| 20  | `merch_lat`             | Double          | Vị trí cửa hàng (Latitude).                   |
| 21  | `merch_long`            | Double          | Vị trí cửa hàng (Longitude).                  |
| 22  | `is_fraud`              | Integer         | Nhãn thực tế (0: Sạch, 1: Gian lận).         |

---

## 3. KIẾN TRÚC HỆ THỐNG (SYSTEM ARCHITECTURE)

Hệ thống được chia thành các tầng (Layers) rõ ràng:

### 3.1. Layer 1: Ingestion (Thu thập)

* **PostgreSQL:** Đóng vai trò là Database nguồn (OLTP).
* **Debezium:** Bắt các thay đổi (CDC) từ Postgres và đẩy vào Kafka.
* **Apache Kafka:** Hàng đợi thông điệp trung gian.

### 3.2. Layer 2: Storage (Lưu trữ - Lakehouse)

* **MinIO:** Object Storage (S3 Compatible).
* **Delta Lake:** Định dạng lưu trữ bảng (Bronze, Silver, Gold).
* **Hive Metastore:** Quản lý metadata.

### 3.3. Layer 3: Processing (Xử lý Stream)

* **Apache Spark (Structured Streaming):** Engine xử lý chính, chạy liên tục 24/7 để chuyển đổi dữ liệu từ Kafka -> Bronze -> Silver -> Gold.

### 3.4. Layer 4: Inference (Dự đoán AI)

* **FastAPI:** Cung cấp API `/predict`. Nhận thông tin giao dịch, trả về kết quả dự đoán gian lận.

### 3.5. Layer 5: Orchestration (Điều phối Batch - Apache Airflow)
Apache Airflow đóng vai trò "Nhạc trưởng" (Orchestrator), chịu trách nhiệm lập lịch và quản lý các quy trình xử lý theo lô (Batch Workflows) chạy định kỳ, tách biệt hoàn toàn với luồng xử lý thời gian thực.

Hệ thống bao gồm 3 DAGs (Directed Acyclic Graphs) chính:

#### **DAG 01: Automated Model Retraining (Tự động huấn luyện lại mô hình)**
*   **Mục tiêu:** Cập nhật mô hình AI để thích nghi với các hành vi gian lận mới (Concept Drift), ngăn chặn việc mô hình bị lỗi thời.
*   **Lịch chạy (Schedule):** 00:00 Hàng ngày (Daily).
*   **Các bước thực hiện (Tasks):**
    1.  **Extract Data:** Spark đọc dữ liệu lịch sử từ bảng **Silver** (ví dụ: dữ liệu 30 ngày gần nhất).
    2.  **Train Model:** Huấn luyện lại mô hình (Random Forest/Logistic Regression) trên tập dữ liệu mới này.
    3.  **Evaluate:** So sánh chỉ số hiệu quả (AUC, F1-Score) của mô hình vừa huấn luyện với mô hình đang chạy hiện tại (Production Model).
    4.  **Register Model:**
        *   Nếu mô hình mới tốt hơn: Đăng ký phiên bản mới vào **MLflow Model Registry** và chuyển trạng thái sang "Production".
        *   Nếu không: Hủy bỏ, giữ nguyên mô hình cũ.

#### **DAG 02: Lakehouse Maintenance (Bảo trì hệ thống Delta Lake)**
*   **Mục tiêu:** Khắc phục vấn đề "Small Files Problem" (nhiều file nhỏ sinh ra do Streaming) giúp tăng tốc độ truy vấn và giải phóng dung lượng lưu trữ.
*   **Lịch chạy:** 02:00 sáng Chủ Nhật hàng tuần (Weekly).
*   **Các bước thực hiện (Tasks):**
    1.  **Optimize Table:** Chạy lệnh `OPTIMIZE` trên các bảng Bronze/Silver để gộp các file Parquet nhỏ thành file lớn hơn.
    2.  **Vacuum Table:** Chạy lệnh `VACUUM` để xóa vật lý các file dữ liệu cũ không còn dùng đến (quá hạn lưu trữ Time Travel, ví dụ: > 7 ngày) để tiết kiệm dung lượng MinIO.

#### **DAG 03: Daily Reporting (Tổng hợp báo cáo ngày)**
*   **Mục tiêu:** Tạo ra các bảng báo cáo tĩnh (Static Reports) để giảm tải cho hệ thống khi Dashboard truy vấn.
*   **Lịch chạy:** 23:55 Hàng ngày.
*   **Các bước thực hiện (Tasks):**
    1.  **Aggregate:** Tính toán tổng số vụ gian lận, tổng thiệt hại tài chính theo từng Bang/Thành phố trong ngày.
    2.  **Write to Gold:** Ghi đè (Overwrite) hoặc nối (Append) kết quả vào bảng `daily_fraud_summary` tại tầng **Gold**.

### 3.6. Layer 6: Query & Consumption (Truy vấn & Sử dụng)

* **Trino (PrestoSQL):** Engine truy vấn SQL phân tán tốc độ cao.
* **Metabase:** Dashboard giám sát.
* **Chatbot (Streamlit + LangChain):** Công cụ xác minh nghiệp vụ.

---

## 4. QUY TRÌNH XỬ LÝ CHI TIẾT (WORKFLOWS)

### 4.1. Luồng xử lý thời gian thực (Real-time Streaming Pipeline)

*Luồng này chạy liên tục, do Spark Streaming đảm nhận, Airflow không can thiệp.*

1. **Phát sinh giao dịch:** Python Producer `INSERT` 1 dòng vào PostgreSQL (Giả lập giao dịch mới).
2. **CDC:** Debezium bắt sự kiện Insert -> Gửi bản tin JSON vào Kafka.
3. **Spark - Bronze Layer:** Spark đọc từ Kafka, ghi dữ liệu thô vào bảng **Bronze** (Append-only).
4. **Spark - Silver Layer (Quan trọng):**
   * Đọc từ Bronze.
   * **Feature Engineering:** Tính `distance_km` (khoảng cách người-cửa hàng), tính `age` (tuổi).
   * **Real-time Inference (Gọi API):** Spark gửi các feature (`amt`, `distance`, `age`...) đến **FastAPI**.
     * *Lưu ý:* Không gửi cột `is_fraud` (đáp án) cho API.
   * **Lưu kết quả:** Lưu vào bảng **Silver** gồm cả cột `is_fraud` (thực tế từ nguồn) và `fraud_prediction` (do API dự đoán) để đối chiếu.
5. **Spark - Gold Layer:** Spark tự động tính toán lại các chỉ số tổng hợp (VD: Số lượng gian lận trong 1 giờ qua) và cập nhật vào bảng **Gold**.

> **Ghi chú về Update/Delete:** Trong phạm vi đồ án này, hệ thống tập trung xử lý luồng **INSERT** (Giao dịch mới). Nếu có Update/Delete từ nguồn, Debezium vẫn bắt được và lưu vào Bronze để truy vết lịch sử, nhưng logic xử lý Silver sẽ ưu tiên dữ liệu mới nhất.

### 4.2. Luồng Batch & Bảo trì (Batch Pipeline)

*Luồng này chạy định kỳ theo lịch, do **Airflow** kích hoạt.*

1. **DAG Model Retraining (00:00 hàng ngày):**
   * Task 1: Spark đọc dữ liệu lịch sử từ bảng **Silver**.
   * Task 2: Huấn luyện lại mô hình (Random Forest/Logistic Regression).
   * Task 3: So sánh độ chính xác với mô hình hiện tại. Nếu tốt hơn -> Đăng ký vào MLflow và cập nhật cho FastAPI.
2. **DAG Lakehouse Maintenance (02:00 hàng tuần):**
   * Task 1: Chạy lệnh `VACUUM` trên các bảng Delta để xóa các file Parquet cũ không còn dùng đến, giải phóng dung lượng MinIO.

### 4.3. Luồng Nghiệp vụ (Business Flow)

1. **Giám sát:** Chuyên viên nhìn Dashboard Metabase, thấy biểu đồ "Gian lận dự đoán" tăng cao.
2. **Điều tra:** Chuyên viên dùng Chatbot hỏi: *"Cho tôi biết chi tiết các giao dịch gian lận tại bang CA trong 10 phút qua"*.
3. **Xử lý:** Chatbot (qua Trino) trả về danh sách -> Chuyên viên xác minh và khóa thẻ.

---

## 5. YÊU CẦU CÔNG NGHỆ & MÔI TRƯỜNG

Hệ thống triển khai trên Docker Compose:

| Thành phần            | Image/Service             | Cổng (Port) | Vai trò                     |
| :---------------------- | :------------------------ | :----------- | :--------------------------- |
| **Source DB**     | `postgres:14`           | 5432         | Nguồn dữ liệu giả lập.  |
| **CDC**           | `debezium/connect`      | 8083         | Bắt thay đổi dữ liệu.   |
| **Kafka**         | `confluentinc/cp-kafka` | 9092         | Hàng đợi thông điệp.   |
| **Storage**       | `minio/minio`           | 9000, 9001   | Data Lake (S3).              |
| **Spark**         | `bitnami/spark`         | 7077, 8080   | Xử lý Stream & Batch.      |
| **Query Engine**  | `trinodb/trino`         | 8082         | Truy vấn SQL tương tác.  |
| **Orchestration** | `apache/airflow`        | 8081         | Điều phối tác vụ Batch. |
| **MLOps**         | `ghcr.io/mlflow/mlflow` | 5000         | Quản lý model.             |
| **Visualization** | `metabase/metabase`     | 3000         | Dashboard.                   |
| **API**           | `fastapi-app`           | 8000         | API dự đoán Real-time.    |
| **Chatbot**       | `streamlit-app`         | 8501         | Giao diện Chatbot.          |

---

## 6. KẾT QUẢ BÀN GIAO (DELIVERABLES)

1. **Mã nguồn (Source Code):** Full stack trên GitHub.
2. **Báo cáo (Report):** Tài liệu thuyết minh chi tiết kiến trúc Lakehouse.
3. **Sản phẩm Demo:**
   * Hệ thống chạy mượt mà từ Ingestion -> Dashboard.
   * Chatbot trả lời đúng câu hỏi nghiệp vụ.
   * Mô hình AI đưa ra dự đoán cho từng giao dịch.
