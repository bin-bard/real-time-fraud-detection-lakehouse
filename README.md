# Hệ Thống Data Lakehouse Phát Hiện Gian Lận Tài Chính Trong Thời Gian Thực

Dự án này là tiểu luận chuyên ngành, trình bày việc thiết kế và triển khai một hệ thống Data Lakehouse toàn diện để phát hiện và hỗ trợ xác minh các giao dịch gian lận thẻ tín dụng trong thời gian thực.

## Mục tiêu

Xây dựng một pipeline dữ liệu end-to-end, có khả năng:

1. **Thu thập** luồng dữ liệu giao dịch gần như tức thời.
2. **Xử lý và làm giàu** dữ liệu trên một kiến trúc Lakehouse tin cậy.
3. **Áp dụng mô hình Machine Learning** để dự đoán và gắn cờ các giao dịch đáng ngờ với độ trễ thấp.
4. **Cung cấp Dashboard** giám sát trực quan các hoạt động gian lận.
5. **Trang bị Chatbot thông minh** cho phép các chuyên viên phân tích điều tra và xác minh cảnh báo bằng ngôn ngữ tự nhiên.

## Kiến trúc và Công nghệ sử dụng

Hệ thống được xây dựng dựa trên kiến trúc Data Lakehouse và áp dụng mô hình xử lý Medallion (Bronze, Silver, Gold). Các công nghệ được sử dụng là các công cụ mã nguồn mở, mạnh mẽ và phổ biến trong ngành dữ liệu lớn.

| Lớp (Layer)               | Công nghệ                                  | Vai trò và Chức năng                                                                                                                                                                                                                                       |
| :------------------------- | :------------------------------------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **1. Ingestion**     | **PostgreSQL, Debezium, Apache Kafka** | Giả lập CSDL nguồn (PostgreSQL), sử dụng Debezium để bắt các thay đổi (CDC) và đẩy vào Kafka dưới dạng luồng sự kiện thời gian thực.                                                                                                    |
| **2. Storage**       | **MinIO, Delta Lake, Hive Metastore**  | Sử dụng MinIO làm Data Lake vật lý, Delta Lake để quản lý các bảng dữ liệu với tính năng ACID và Time Travel, và Hive Metastore làm catalog trung tâm.                                                                                     |
| **3. Processing**    | **Apache Spark, Trino**                | **Spark (Structured Streaming)** là engine chính để xử lý luồng, làm giàu dữ liệu và phát hiện gian lận. **Trino** là engine truy vấn SQL tốc độ cao, phục vụ cho nhu cầu truy vấn tương tác từ Dashboard và Chatbot. |
| **4. ML & MLOps**    | **MLflow, FastAPI**                    | **MLflow** quản lý toàn bộ vòng đời mô hình (huấn luyện, lưu trữ, đăng ký). Mô hình tốt nhất được đóng gói và phục vụ (serving) thông qua một **API service bằng FastAPI**.                                        |
| **5. Orchestration** | **Apache Airflow**                     | Điều phối các pipeline xử lý theo lô (batch), chẳng hạn như tác vụ huấn luyện lại mô hình hàng đêm.                                                                                                                                        |
| **6. Visualization** | **Metabase**                           | Xây dựng Dashboard giám sát gian lận (Fraud Monitoring Dashboard) trực quan, kết nối với Trino để có hiệu năng cao.                                                                                                                              |
| **7. Verification**  | **Streamlit, LangChain, OpenAI API**   | Xây dựng ứng dụng**Chatbot "Trợ lý Phân tích Gian lận"**: Giao diện bằng **Streamlit**, logic xử lý bằng **LangChain**, và khả năng hiểu ngôn ngữ tự nhiên từ **API của OpenAI**.                              |

## Cấu trúc thư mục

```text
real-time-fraud-detection-lakehouse/
├── airflow/
│   ├── dags/ # DAGs Airflow (huấn luyện lại, báo cáo)
│   └── plugins/ # Plugins mở rộng (nếu cần)
├── config/ # CẤU HÌNH TẬP TRUNG
│   ├── metastore/hive-site.xml # Kết nối Hive Metastore (Postgres, driver, creds)
│   ├── spark/spark-defaults.conf # Mở rộng Delta Lake, tinh chỉnh Spark
│   └── trino/config.properties # Cấu hình Trino coordinator
├── data/ # Dữ liệu nguồn/bộ mẫu Kaggle
├── docs/ # Tài liệu, sơ đồ kiến trúc
├── notebooks/ # Phân tích & thử nghiệm mô hình
├── scripts/ # Script tiện ích (khởi tạo DB, dọn dẹp)
│   ├── init_postgres.sql
│   └── cleanup.sh
├── services/ # Các service (API, chatbot, producer)
│   ├── fraud-detection-api/
│   ├── chatbot-app/
│   └── data-producer/
├── spark/
│   ├── app/ # Jobs Spark (streaming + batch)
│   │   ├── streaming_job.py
│   │   └── batch_job.py
│   ├── app/jars/ # JAR Delta Lake
│   │   └── delta-core_2.12-x.x.x.jar
│   └── requirements.txt # Python cho Spark (pyspark, delta-spark)
├── docker-compose.yml
├── .env
├── .gitignore
└── README.md
```

## Dữ liệu

Dự án sử dụng bộ dữ liệu công khai **Credit Card Fraud Detection** từ Kaggle.

- **Nguồn:** [https://www.kaggle.com/datasets/mlg-ulb/creditcardfraud](https://www.kaggle.com/datasets/mlg-ulb/creditcardfraud)
- **Đặc điểm:** Dữ liệu chứa các giao dịch thẻ tín dụng trong 2 ngày tại Châu Âu. Dữ liệu có tính mất cân bằng cao (0.172% là gian lận), phản ánh đúng thách thức của bài toán trong thực tế.

## Hướng dẫn cài đặt và chạy dự án

1. **Yêu cầu:**

   - Docker & Docker Compose
   - Tài khoản OpenAI và API Key
2. **Các bước thực hiện:**

   - Clone repository này: `git clone https://github.com/bin-bard/real-time-fraud-detection-lakehouse.git`
   - Điền các thông tin cần thiết (API Key, credentials) vào file `.env`.
   - Chạy toàn bộ hệ thống bằng Docker Compose: `docker-compose up -d`
   - Truy cập các dịch vụ qua các cổng (port) đã được cấu hình.
