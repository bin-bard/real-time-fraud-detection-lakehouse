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

| Lớp (Layer)          | Công nghệ                              | Vai trò và Chức năng                                                                                                                                                                                                  |
| :------------------- | :------------------------------------- | :-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **1. Ingestion**     | **PostgreSQL, Debezium, Apache Kafka** | Giả lập CSDL nguồn (PostgreSQL), sử dụng Debezium để bắt các thay đổi (CDC) và đẩy vào Kafka dưới dạng luồng sự kiện thời gian thực.                                                                                  |
| **2. Storage**       | **MinIO, Delta Lake, Hive Metastore**  | Sử dụng MinIO làm Data Lake vật lý, Delta Lake để quản lý các bảng dữ liệu với tính năng ACID và Time Travel, và Hive Metastore làm catalog trung tâm.                                                                |
| **3. Processing**    | **Apache Spark, Trino**                | **Spark (Structured Streaming)** là engine chính để xử lý luồng, làm giàu dữ liệu và phát hiện gian lận. **Trino** là engine truy vấn SQL tốc độ cao, phục vụ cho nhu cầu truy vấn tương tác từ Dashboard và Chatbot. |
| **4. ML & MLOps**    | **MLflow, FastAPI**                    | **MLflow** quản lý toàn bộ vòng đời mô hình (huấn luyện, lưu trữ, đăng ký). Mô hình tốt nhất được đóng gói và phục vụ (serving) thông qua một **API service bằng FastAPI**.                                           |
| **5. Orchestration** | **Apache Airflow**                     | Điều phối các pipeline xử lý theo lô (batch), chẳng hạn như tác vụ huấn luyện lại mô hình hàng đêm.                                                                                                                   |
| **6. Visualization** | **Metabase**                           | Xây dựng Dashboard giám sát gian lận (Fraud Monitoring Dashboard) trực quan, kết nối với Trino để có hiệu năng cao.                                                                                                   |
| **7. Verification**  | **Streamlit, LangChain, OpenAI API**   | Xây dựng ứng dụng**Chatbot "Trợ lý Phân tích Gian lận"**: Giao diện bằng **Streamlit**, logic xử lý bằng **LangChain**, và khả năng hiểu ngôn ngữ tự nhiên từ **API của OpenAI**.                                     |

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

### 1. Yêu cầu hệ thống

- **Docker & Docker Compose** (phiên bản mới nhất)
- **Python 3.9+** với pip
- **Git**
- Tối thiểu **8GB RAM** và **20GB dung lượng trống**

### 2. Cài đặt dự án

```bash
# Clone repository
git clone https://github.com/bin-bard/real-time-fraud-detection-lakehouse.git
cd real-time-fraud-detection-lakehouse
```

### 3. Khởi động hệ thống

#### Bước 1: Khởi động toàn bộ infrastructure

```bash
# Khởi động tất cả services
docker-compose up -d

# Kiểm tra status
docker ps
```

#### Bước 2: Khởi tạo Data Lakehouse

```bash
# Setup MinIO buckets và folder structure
docker-compose --profile setup run --rm minio-setup
```

**Kết quả mong đợi:**

```
🔧 MinIO Data Lakehouse Setup Script
✅ MinIO is ready!
✅ Bucket 'lakehouse' created successfully.
🎉 MinIO setup completed successfully!
```

#### Bước 3: Kiểm tra các services

```bash
# Xem logs các services
docker logs kafka
docker logs data-producer
docker logs minio

# Kiểm tra tất cả containers
docker ps
```

### 4. Truy cập các dịch vụ

| Service             | URL                     | Username | Password |
| ------------------- | ----------------------- | -------- | -------- |
| **Spark Master UI** | http://localhost:8080   | -        | -        |
| **MinIO Console**   | http://localhost:9001   | minio    | minio123 |
| **Kafka**           | localhost:9092          | -        | -        |
| **Hive Metastore**  | thrift://localhost:9083 | -        | -        |

### 5. Chạy Spark Streaming Job

**Lưu ý**: Sử dụng Spark 3.4.1 để tương thích với Delta Lake 2.4.0

```bash
# Chạy streaming job trực tiếp từ PowerShell/Terminal
docker exec -it spark-master bash -c "/opt/spark/bin/spark-submit --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.4.1,io.delta:delta-core_2.12:2.4.0,org.apache.hadoop:hadoop-aws:3.3.4 --conf 'spark.sql.extensions=io.delta.sql.DeltaSparkSessionExtension' --conf 'spark.sql.catalog.spark_catalog=org.apache.spark.sql.delta.catalog.DeltaCatalog' /app/streaming_job.py"
```

**Hoặc có thể vào container để debug:**

```bash
# Vào Spark Master container
docker exec -it spark-master bash

# Chạy streaming job với Delta Lake
/opt/spark/bin/spark-submit \
    --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.4.1,io.delta:delta-core_2.12:2.4.0,org.apache.hadoop:hadoop-aws:3.3.4 \
    --conf 'spark.sql.extensions=io.delta.sql.DeltaSparkSessionExtension' \
    --conf 'spark.sql.catalog.spark_catalog=org.apache.spark.sql.delta.catalog.DeltaCatalog' \
    /app/streaming_job.py
```

**Kết quả mong đợi:**

```
✅ Spark Session with Delta Lake created successfully.
Bronze layer streaming started. Writing to MinIO...
Writing batch 0 to Bronze layer...
Batch 0 written to Bronze successfully.
Writing batch 1 to Bronze layer...
Batch 1 written to Bronze successfully.
...
```

### 6. Kiểm tra dữ liệu

#### Kiểm tra Kafka data:

```bash
# Vào kafka container
docker exec -it kafka bash

# Xem data trong topic
kafka-console-consumer --bootstrap-server localhost:9092 --topic credit_card_transactions --from-beginning --max-messages 5
```

#### Kiểm tra Delta Lake data trong MinIO:

1. **Truy cập MinIO Console**: http://localhost:9001

   - Username: `minio`
   - Password: `minio123`

2. **Browse bucket `lakehouse`**

3. **Kiểm tra các folder:**
   - `bronze/transactions/` - Raw transaction data từ Kafka
   - `checkpoints/bronze/` - Spark streaming checkpoints
   - Các file Parquet được tạo theo partition `year/month/day`

#### Kiểm tra Spark Streaming đang chạy:

```bash
# Kiểm tra Spark UI
# Truy cập: http://localhost:8080
# Xem Streaming tab để theo dõi job

# Hoặc kiểm tra logs
docker logs spark-master
```

### 7. Troubleshooting

#### Lỗi thường gặp:

**1. Hive Metastore schema error:**

```bash
# Reset volumes và restart
docker-compose down -v
docker-compose up -d
docker-compose --profile setup run --rm minio-setup
```

**2. Spark-Delta Lake compatibility error:**

- Đảm bảo sử dụng Spark 3.4.1 với Delta Lake 2.4.0
- Version packages trong spark-submit phải match

**3. MinIO bucket not found:**

```bash
# Chạy lại setup
docker-compose --profile setup run --rm minio-setup
```

#### Monitoring và logs:

```bash
# Xem logs real-time
docker logs -f data-producer
docker logs -f spark-master
docker logs -f minio

# Restart specific service
docker-compose restart kafka
docker-compose restart spark-master

# Reset toàn bộ hệ thống (xóa dữ liệu)
docker-compose down -v
docker-compose up -d
docker-compose --profile setup run --rm minio-setup
```

### 8. Architecture Verification

Sau khi setup thành công, bạn sẽ có:

1. **✅ Data Ingestion**: Credit card transactions được stream từ CSV → Kafka
2. **✅ Data Lake**: MinIO với structure Bronze/Silver/Gold
3. **✅ Stream Processing**: Spark đọc từ Kafka và ghi vào Delta Lake với ACID transactions
4. **✅ Metadata Management**: Hive Metastore quản lý table schemas
5. **✅ Storage Format**: Delta Lake cung cấp ACID transactions và Time Travel

**Kiểm tra hoạt động:**

- **Kafka Producer**: `docker logs data-producer` - data được publish liên tục
- **Spark Streaming**: Batch processing messages hiển thị "Batch X written to Bronze successfully"
- **MinIO Storage**: Parquet files xuất hiện trong `lakehouse/bronze/transactions/`
- **Delta Lake**: Transaction logs trong `_delta_log/` folder

### 9. Tiếp theo

Sau khi Data Lakehouse hoạt động ổn định, các bước phát triển tiếp theo:

- 🤖 **Machine Learning Pipeline**: Huấn luyện mô hình fraud detection với MLflow
- 📊 **Analytics Dashboard**: Metabase cho real-time fraud monitoring
- 🤖 **AI Chatbot**: LangChain + OpenAI để intelligent querying
- 🔄 **Workflow Orchestration**: Airflow cho automated model retraining
- 🥈 **Silver Layer**: Data transformation và feature engineering
- 🥇 **Gold Layer**: Aggregated analytics và business metrics

### 10. Cấu trúc dữ liệu Lakehouse

```
s3a://lakehouse/
├── bronze/           # Raw data từ Kafka
│   └── transactions/
├── silver/           # Cleaned & enriched data
│   ├── transactions/
│   └── features/
├── gold/             # Aggregated analytics data
│   ├── aggregated/
│   └── reports/
├── checkpoints/      # Spark streaming checkpoints
│   ├── bronze/
│   ├── silver/
│   └── gold/
└── models/           # ML models
    ├── fraud_detection/
    └── experiments/
```
