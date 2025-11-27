
# ĐẶC TẢ YÊU CẦU DỰ ÁN (PROJECT SPECIFICATION)

**Tên đề tài:** Xây dựng hệ thống Data Lakehouse để phát hiện và xác minh gian lận tài chính trong thời gian thực.
**Nhóm thực hiện:** Nhóm 6
**Thành viên:**

1. Nguyễn Thanh Tài - 22133049
2. Võ Triệu Phúc - 22133043
   **GVHD:** ThS. Phan Thị Thể
   **Phiên bản:** 3.1 (Đã kiểm tra kỹ Schema Dataset Sparkov)

---

## 1. TỔNG QUAN DỰ ÁN (PROJECT OVERVIEW)

### 1.1. Mục tiêu cốt lõi

Dự án nhằm xây dựng một **Modern Data Platform (Nền tảng dữ liệu hiện đại)** toàn diện, giải quyết bài toán phát hiện gian lận thẻ tín dụng với các tiêu chí:

1. **Real-time Ingestion:** Bắt các thay đổi dữ liệu (CDC) từ hệ thống giao dịch nguồn ngay lập tức.
2. **Lakehouse Architecture:** Kết hợp độ tin cậy của Data Warehouse và khả năng mở rộng của Data Lake.
3. **MLOps khép kín:** Tự động hóa quy trình huấn luyện và triển khai mô hình học máy.
4. **Nghiệp vụ thông minh:** Cung cấp Dashboard giám sát và Chatbot trợ lý ảo cho chuyên viên điều tra.

### 1.2. Phạm vi

Hệ thống xử lý luồng dữ liệu giả lập từ 01/01/2019 đến 31/12/2020, mô phỏng hoạt động của 1000 khách hàng và 800 nhà bán hàng.

---

## 2. DỮ LIỆU SỬ DỤNG (DATASET)

**Tên bộ dữ liệu:** Credit Card Transactions Fraud Detection Dataset (Sparkov Data Generation).
**Nguồn:** [Kaggle - Kartik Shenoy](https://www.kaggle.com/datasets/kartik2112/fraud-detection)

### Schema chi tiết (Dữ liệu đầu vào):

*Lưu ý: Bỏ qua cột Index (số thứ tự dòng) đầu tiên trong file CSV.*

| STT | Tên cột                 | Kiểu dữ liệu | Ý nghĩa nghiệp vụ                                     |
| :-- | :------------------------ | :-------------- | :-------------------------------------------------------- |
| 1   | `trans_date_trans_time` | DateTime        | Thời gian giao dịch (VD: 01/01/2019 00:00).             |
| 2   | `cc_num`                | Long            | Số thẻ tín dụng (ID khách hàng).                    |
| 3   | `merchant`              | String          | Tên đơn vị bán hàng (VD: fraud_Rippin).             |
| 4   | `category`              | String          | Danh mục (VD: grocery_pos, gas_transport).               |
| 5   | `amt`                   | Double          | Số tiền giao dịch.                                     |
| 6   | `first`                 | String          | Tên đệm.                                               |
| 7   | `last`                  | String          | Họ.                                                      |
| 8   | `gender`                | String          | Giới tính (M/F).                                        |
| 9   | `street`                | String          | Địa chỉ đường.                                      |
| 10  | `city`                  | String          | Thành phố.                                              |
| 11  | `state`                 | String          | Bang (VD: NC, NY).                                        |
| 12  | `zip`                   | Integer         | Mã bưu chính.                                          |
| 13  | `lat`                   | Double          | **Vĩ độ của chủ thẻ (Customer Latitude).**    |
| 14  | `long`                  | Double          | **Kinh độ của chủ thẻ (Customer Longitude).**  |
| 15  | `city_pop`              | Integer         | Dân số thành phố.                                     |
| 16  | `job`                   | String          | Nghề nghiệp.                                            |
| 17  | `dob`                   | Date            | Ngày sinh (Dùng tính tuổi).                           |
| 18  | `trans_num`             | String          | Mã giao dịch duy nhất (Transaction ID).                |
| 19  | `unix_time`             | Long            | Thời gian dạng Unix Timestamp (VD: 1325376018).         |
| 20  | `merch_lat`             | Double          | **Vĩ độ của cửa hàng (Merchant Latitude).**   |
| 21  | `merch_long`            | Double          | **Kinh độ của cửa hàng (Merchant Longitude).** |
| 22  | `is_fraud`              | Integer         | Nhãn gian lận (0: Thường, 1: Gian lận).              |

---

## 3. KIẾN TRÚC HỆ THỐNG (SYSTEM ARCHITECTURE)

Hệ thống tuân thủ mô hình **Lakehouse** với các lớp công nghệ sau:

### 3.1. Layer 1: Ingestion (Thu thập dữ liệu)

* **PostgreSQL:** Đóng vai trò là Cơ sở dữ liệu giao dịch nguồn (Source OLTP). Một Python Script sẽ "bơm" dữ liệu từ file CSV vào đây theo thời gian thực.
* **Debezium:** Công cụ Change Data Capture (CDC). Lắng nghe transaction log của PostgreSQL và bắt mọi sự kiện `INSERT` mới.
* **Apache Kafka:** Message Queue nhận luồng sự kiện từ Debezium, đảm bảo đệm dữ liệu tin cậy trước khi xử lý.

### 3.2. Layer 2: Storage (Lưu trữ - The Lakehouse)

* **MinIO:** Object Storage (S3 Compatible), nơi lưu trữ vật lý của Data Lake.
* **Delta Lake:** Định dạng lưu trữ bảng, cung cấp tính năng ACID Transaction, Schema Enforcement và Time Travel.
* **Hive Metastore:** Quản lý metadata (cấu trúc bảng) trung tâm.

### 3.3. Layer 3: Processing (Xử lý dữ liệu)

Sử dụng **Apache Spark** thực hiện mô hình **Medallion Architecture**:

* **Bronze Table:** Chứa dữ liệu thô (Raw JSON) đọc từ Kafka.
* **Silver Table:** Dữ liệu đã làm sạch, chuẩn hóa kiểu dữ liệu, và **Feature Engineering** (Tính `distance_km` từ tọa độ `lat/long` và `merch_lat/merch_long`; tính `age` từ `dob`).
* **Gold Table:** Dữ liệu tổng hợp (Aggregated) phục vụ báo cáo (VD: Tổng gian lận theo Bang, theo Merchant).

### 3.4. Layer 4: ML & MLOps (Học máy & Vận hành)

* **MLflow:**
  * **Tracking:** Ghi lại các tham số, metrics (AUC, Accuracy) của các lần thử nghiệm mô hình.
  * **Model Registry:** Quản lý phiên bản mô hình (Staging/Production).
* **FastAPI:** Đóng gói mô hình đã huấn luyện (từ MLflow) thành API RESTful (`/predict`) để phục vụ dự đoán thời gian thực.

### 3.5. Layer 5: Orchestration (Điều phối - Apache Airflow)

Airflow đóng vai trò "Nhạc trưởng" quản lý toàn bộ hệ thống batch:

* **DAG 1 - Model Retraining:** Chạy hàng đêm. Đọc dữ liệu Silver mới nhất -> Train lại model -> Đánh giá -> Nếu tốt hơn model cũ thì đăng ký vào MLflow Registry.
* **DAG 2 - Data Maintenance:** Chạy định kỳ. Thực hiện lệnh `VACUUM` và `OPTIMIZE` trên các bảng Delta Lake để dọn dẹp file rác và tối ưu hiệu suất đọc.
* **DAG 3 - Daily Reporting:** Chạy cuối ngày. Tổng hợp dữ liệu từ Silver -> Ghi vào bảng Gold (Report Table) để Dashboard load nhanh hơn.

### 3.6. Layer 6: Query & Visualization (Truy vấn & Hiển thị)

* **Trino (PrestoSQL):** Engine truy vấn SQL phân tán, cho phép truy vấn trực tiếp trên Delta Lake/MinIO với tốc độ cực nhanh.
* **Metabase:** Dashboard kết nối tới Trino để hiển thị biểu đồ.

### 3.7. Layer 7: Verification (Xác minh & Tương tác)

* **Chatbot (Streamlit + LangChain + OpenAI):**
  * Kết nối với Trino.
  * Cho phép người dùng hỏi bằng ngôn ngữ tự nhiên (VD: *"Liệt kê 5 giao dịch gian lận lớn nhất tại New York"*).
  * LangChain chuyển câu hỏi thành SQL -> Trino thực thi -> Trả kết quả lại cho Chatbot.

---

## 4. QUY TRÌNH XỬ LÝ CHI TIẾT (WORKFLOWS)

### 4.1. Luồng xử lý thời gian thực (Real-time Pipeline)

1. **Simulation:** Python script insert 1 giao dịch vào PostgreSQL.
2. **Capture:** Debezium bắt sự kiện -> Gửi JSON vào Kafka topic `transactions`.
3. **Stream Processing (Spark):**
   * Đọc Kafka.
   * Lưu vào **Bronze**.
   * Biến đổi, tính toán đặc trưng (Feature Engineering) -> Lưu vào **Silver**.
   * (Optional) Gọi API FastAPI để lấy điểm gian lận (Fraud Score).
4. **Monitoring:** Dữ liệu Silver xuất hiện trên Metabase Dashboard ngay lập tức.

### 4.2. Luồng xác minh nghiệp vụ (Investigation Flow)

1. Hệ thống cảnh báo giao dịch nghi ngờ.
2. Chuyên viên mở **Chatbot Streamlit**.
3. Nhập lệnh: *"Kiểm tra lịch sử giao dịch của thẻ 123456 trong 30 ngày qua"*.
4. Chatbot query Trino -> Hiển thị danh sách giao dịch, vị trí địa lý, merchant.
5. Chuyên viên xác nhận gian lận hay không.

### 4.3. Luồng MLOps & Bảo trì (Batch Flow - Airflow)

1. **00:00 hàng ngày:** Airflow kích hoạt DAG Retrain.
2. Spark đọc dữ liệu lịch sử từ Silver -> Train Random Forest model.
3. Log kết quả vào MLflow.
4. Nếu Model mới tốt hơn -> Update API FastAPI.
5. **02:00 hàng ngày:** Airflow kích hoạt DAG Maintenance -> Clean up Data Lake.

---

## 5. YÊU CẦU CÔNG NGHỆ & MÔI TRƯỜNG

Hệ thống được triển khai hoàn toàn trên **Docker & Docker Compose**.

| Thành phần            | Image/Service                    | Cổng (Port) |
| :---------------------- | :------------------------------- | :----------- |
| **Source DB**     | `postgres:14`                  | 5432         |
| **CDC**           | `debezium/connect`             | 8083         |
| **Message Queue** | `confluentinc/cp-kafka`        | 9092         |
| **Storage**       | `minio/minio`                  | 9000, 9001   |
| **Orchestration** | `apache/airflow`               | 8080         |
| **Processing**    | `bitnami/spark`                | 7077, 8081   |
| **Query Engine**  | `trinodb/trino`                | 8082         |
| **Visualization** | `metabase/metabase`            | 3000         |
| **MLOps**         | `ghcr.io/mlflow/mlflow`        | 5000         |
| **Serving API**   | `fastapi-app` (Custom build)   | 8000         |
| **Chatbot**       | `streamlit-app` (Custom build) | 8501         |

---

## 6. KẾT QUẢ BÀN GIAO (DELIVERABLES)

1. **Source Code:** Repository GitHub chứa toàn bộ mã nguồn, Dockerfile, DAGs, Notebooks.
2. **Tài liệu báo cáo:** Thuyết minh kiến trúc, quy trình xử lý, giải thích thuật toán ML.
3. **Hệ thống Demo:**
   * Dashboard Metabase cập nhật realtime.
   * Airflow UI hiển thị các DAGs chạy thành công.
   * Chatbot trả lời câu hỏi nghiệp vụ chính xác.
   * MLflow UI hiển thị quá trình tracking model.
