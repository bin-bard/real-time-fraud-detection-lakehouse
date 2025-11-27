# Hệ Thống Data Lakehouse Phát Hiện Gian Lận Tài Chính Trong Thời Gian Thực

Dự án này là tiểu luận chuyên ngành, trình bày việc thiết kế và triển khai một hệ thống Data Lakehouse toàn diện để phát hiện và hỗ trợ xác minh các giao dịch gian lận thẻ tín dụng trong thời gian thực.

![Architecture Diagram](docs/architecture.png)

## Mục tiêu

Xây dựng một pipeline dữ liệu end-to-end, có khả năng:

1. **Thu thập** luồng dữ liệu giao dịch gần như tức thời từ PostgreSQL qua Debezium CDC.
2. **Xử lý và làm giàu** dữ liệu trên một kiến trúc Lakehouse tin cậy với Delta Lake.
3. **Áp dụng mô hình Machine Learning** để dự đoán và gắn cờ các giao dịch đáng ngờ với độ trễ thấp.
4. **Cung cấp Dashboard** giám sát trực quan các hoạt động gian lận (coming soon).
5. **Trang bị Chatbot thông minh** cho phép các chuyên viên phân tích điều tra và xác minh cảnh báo bằng ngôn ngữ tự nhiên (coming soon).

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

Dự án sử dụng bộ dữ liệu công khai **Sparkov Credit Card Transactions Fraud Detection Dataset** từ Kaggle.

- **Nguồn:** [https://www.kaggle.com/datasets/kartik2112/fraud-detection](https://www.kaggle.com/datasets/kartik2112/fraud-detection)
- **Files:**
  - `data/fraudTrain.csv` - Training dataset (1,296,675 transactions)
  - `data/fraudTest.csv` - Test dataset (555,719 transactions)
- **Đặc điểm:** Dữ liệu chứa các giao dịch thẻ tín dụng được tạo bởi Sparkov Data Generation từ 01/01/2019 đến 31/12/2020. Bộ dữ liệu bao gồm thông tin địa lý chi tiết (vĩ độ/kinh độ của khách hàng và cửa hàng), thông tin nhân khẩu học (tuổi, giới tính, nghề nghiệp), và các đặc điểm giao dịch thực tế.

### Schema Dữ Liệu

| Cột                              | Kiểu dữ liệu | Mô tả                                                |
| -------------------------------- | ------------ | ---------------------------------------------------- |
| `trans_date_trans_time`          | DateTime     | Thời gian giao dịch                                  |
| `cc_num`                         | Long         | Số thẻ tín dụng                                      |
| `merchant`                       | String       | Tên cửa hàng                                         |
| `category`                       | String       | Danh mục sản phẩm (grocery_pos, gas_transport, etc.) |
| `amt`                            | Double       | Số tiền giao dịch                                    |
| `first`, `last`                  | String       | Họ tên khách hàng                                    |
| `gender`                         | String       | Giới tính (M/F)                                      |
| `street`, `city`, `state`, `zip` | String/Int   | Địa chỉ khách hàng                                   |
| `lat`, `long`                    | Double       | **Vị trí địa lý khách hàng**                         |
| `city_pop`                       | Integer      | Dân số thành phố                                     |
| `job`                            | String       | Nghề nghiệp                                          |
| `dob`                            | Date         | Ngày sinh                                            |
| `trans_num`                      | String       | Mã giao dịch (unique identifier)                     |
| `unix_time`                      | Long         | Unix timestamp                                       |
| `merch_lat`, `merch_long`        | Double       | **Vị trí địa lý cửa hàng**                           |
| `is_fraud`                       | Integer      | Nhãn gian lận (0: Normal, 1: Fraud)                  |

### Features Engineering (Silver Layer)

Hệ thống tự động tạo **15 features** từ dữ liệu gốc:

1. **Geographic Features:**

   - `distance_km`: Khoảng cách Haversine giữa khách hàng và cửa hàng
   - `is_distant_transaction`: Cờ giao dịch xa (>100km)

2. **Demographic Features:**

   - `age`: Tuổi tính từ ngày sinh
   - `gender_encoded`: Mã hóa giới tính (0/1)

3. **Time Features:**

   - `hour`, `day_of_week`, `is_weekend`
   - `hour_sin`, `hour_cos`: Cyclic encoding cho giờ
   - `is_late_night`: Cờ giao dịch đêm khuya (11PM-5AM)

4. **Transaction Amount Features:**
   - `log_amount`: Log transformation của số tiền
   - `amount_bin`: Phân loại khoảng tiền (0-5)
   - `is_zero_amount`, `is_high_amount`: Cờ số tiền đặc biệt

## Hướng dẫn cài đặt và chạy dự án

> **⚠️ QUAN TRỌNG - ĐÃ CẬP NHẬT LÊN SPARKOV DATASET (v2.0)**
>
> Dự án đã được **hoàn toàn cập nhật** để sử dụng bộ dữ liệu **Sparkov Credit Card Transactions** thay vì dataset PCA cũ.
>
> **Thay đổi chính:**
>
> - ✅ Dataset: `fraudTrain.csv` & `fraudTest.csv` (thay vì `creditcard.csv`)
> - ✅ Schema: 22 cột với thông tin địa lý, nhân khẩu học đầy đủ (thay vì V1-V28 PCA)
> - ✅ Feature Engineering: Distance (Haversine), Age, Time features (thay vì PCA interactions)
> - ✅ Ingestion: PostgreSQL + Debezium CDC (thay vì Kafka trực tiếp)
> - ✅ Bronze Layer: Raw Sparkov transactions
> - ✅ Silver Layer: 15 engineered features cho ML
> - ✅ Gold Layer: Geographic, category, state aggregations
> - ✅ ML Training: Random Forest với balanced sampling
> - ✅ FastAPI: Endpoints cho Sparkov features
>
> **Chi tiết:** Xem file `docs/PROJECT_SPECIFICATION.md` để hiểu rõ kiến trúc và yêu cầu.

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

### 5. Chạy ML Pipeline và Feature Engineering

**⚠️ THỨ TỰ QUAN TRỌNG**: Phải chạy streaming pipeline trước để có dữ liệu Bronze layer!

#### Bước 1: Start Real-time Data Streaming (BẮT BUỘC ĐẦU TIÊN)

```bash
# 1.1. Start data producer để sinh fake transactions
docker-compose up -d data-producer

# 1.2. Start Spark streaming job để ghi vào Bronze layer
docker exec -it spark-master bash -c "/opt/spark/bin/spark-submit --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.4.1,io.delta:delta-core_2.12:2.4.0,org.apache.hadoop:hadoop-aws:3.3.4 --conf 'spark.sql.extensions=io.delta.sql.DeltaSparkSessionExtension' --conf 'spark.sql.catalog.spark_catalog=org.apache.spark.sql.delta.catalog.DeltaCatalog' /app/streaming_job.py" &

# 1.3. Để streaming chạy ít nhất 2-3 phút để có đủ data
# Bạn có thể Ctrl+C để dừng streaming job khi đã có đủ data
```

**📊 Kiểm tra dữ liệu Bronze layer:**

```bash
# Check MinIO có bronze data chưa
docker exec -it minio mc alias set minio http://localhost:9000 minio minio123
docker exec -it minio mc ls minio/lakehouse/bronze/transactions/ --recursive
```

#### Bước 2: Cài đặt thư viện ML cho Spark (Required)

**⚠️ Quan trọng**: Spark containers cần cài đặt thêm thư viện ML để chạy training pipeline:

```bash
# Cài đặt cho Spark Master (bắt buộc)
docker exec -it spark-master bash -c "pip install numpy pandas scikit-learn mlflow boto3 psycopg2-binary"

# Cài đặt cho Spark Worker (khuyến nghị cho distributed processing)
docker exec -it spark-worker bash -c "pip install numpy pandas scikit-learn mlflow boto3 psycopg2-binary"
```

**Lưu ý về dependency conflicts:**

- Error `urllib3 2.2.3 incompatible` có thể xuất hiện nhưng không ảnh hưởng chức năng
- Các thư viện ML vẫn hoạt động bình thường với warning này

#### Bước 3: Chạy Silver Layer Processing (Feature Engineering)

```bash
# Chạy Silver layer job để tạo features cho ML
docker exec -it spark-master bash -c "/opt/spark/bin/spark-submit --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.4.1,io.delta:delta-core_2.12:2.4.0,org.apache.hadoop:hadoop-aws:3.3.4 --conf 'spark.sql.extensions=io.delta.sql.DeltaSparkSessionExtension' --conf 'spark.sql.catalog.spark_catalog=org.apache.spark.sql.delta.catalog.DeltaCatalog' /app/silver_layer_job.py"
```

**Kết quả mong đợi:**

```
🥈 Starting Bronze to Silver layer processing...
Reading from Bronze layer...
Bronze data count: 6621
Performing data quality checks...
Starting feature engineering...
Feature engineering completed. Total features: 42
Writing to Silver layer...
✅ Silver layer processing completed successfully!
📊 Silver Layer Statistics:
   Total transactions: 6610
   Normal transactions: 6558 (99.21%)
   Fraudulent transactions: 52 (0.79%)
```

#### Bước 4: Chạy ML Training Pipeline

```bash
# Huấn luyện models với Random Forest và Logistic Regression
docker exec -it spark-master bash -c "/opt/spark/bin/spark-submit --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.4.1,io.delta:delta-core_2.12:2.4.0,org.apache.hadoop:hadoop-aws:3.3.4 --conf 'spark.sql.extensions=io.delta.sql.DeltaSparkSessionExtension' --conf 'spark.sql.catalog.spark_catalog=org.apache.spark.sql.delta.catalog.DeltaCatalog' /app/ml_training_job.py"
```

**Kết quả mong đợi:**

```
🔄 Training random_forest model...
📊 Model Performance:
   AUC: 0.9999
   Accuracy: 0.9976
   Precision: 0.9976
   Recall: 0.9976
   F1-Score: 0.9976
   Fraud Detection Rate: 0.8333

🔄 Training logistic_regression model...
📊 Model Performance:
   AUC: 0.9993
   Accuracy: 0.9953
   Precision: 0.9950
   Recall: 0.9953
   F1-Score: 0.9951
   Fraud Detection Rate: 0.6667

🎉 All models training completed!
```

#### Bước 5: Kiểm tra ML Pipeline

**Kiểm tra Silver layer data:**

1. Truy cập MinIO Console: http://localhost:9001
2. Browse `lakehouse/silver/transactions/` để xem transformed data
3. Verify 42 features đã được tạo

**Kiểm tra Gold layer data (optional):**

```bash
# Chạy Gold layer aggregation
docker exec -it spark-master bash -c "/opt/spark/bin/spark-submit --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.4.1,io.delta:delta-core_2.12:2.4.0,org.apache.hadoop:hadoop-aws:3.3.4 --conf 'spark.sql.extensions=io.delta.sql.DeltaSparkSessionExtension' --conf 'spark.sql.catalog.spark_catalog=org.apache.spark.sql.delta.catalog.DeltaCatalog' /app/gold_layer_job.py"
```

### 6. Chạy Spark Streaming Job

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

### 7. Kiểm tra dữ liệu

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

### 8. Troubleshooting

#### Lỗi thường gặp:

**1. ML Library Dependency Conflicts:**

```bash
# Error: urllib3 2.2.3 incompatible
# Giải pháp: Warning này không ảnh hưởng chức năng, có thể bỏ qua
# Hoặc force reinstall specific versions:
docker exec -it spark-master bash -c "pip install urllib3==1.26.20 --force-reinstall"
```

**2. MLflow Connection Refused:**

```bash
# Nếu MLflow tracking server chưa ready
docker-compose restart mlflow
docker logs mlflow  # Check logs

# MLflow đang tạm thời disabled trong training code để test
# Sẽ được enable sau khi fix network connectivity
```

**3. Hive Metastore schema error:**

```bash
# Reset volumes và restart
docker-compose down -v
docker-compose up -d
docker-compose --profile setup run --rm minio-setup
```

**4. Spark-Delta Lake compatibility error:**

- Đảm bảo sử dụng Spark 3.4.1 với Delta Lake 2.4.0
- Version packages trong spark-submit phải match

**5. MinIO bucket not found:**

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

### 9. Architecture Verification

Sau khi setup thành công, bạn sẽ có:

1. **✅ Data Ingestion**: Credit card transactions được stream từ CSV → Kafka
2. **✅ Data Lake**: MinIO với structure Bronze/Silver/Gold
3. **✅ Stream Processing**: Spark đọc từ Kafka và ghi vào Delta Lake với ACID transactions
4. **✅ Metadata Management**: Hive Metastore quản lý table schemas
5. **✅ Storage Format**: Delta Lake cung cấp ACID transactions và Time Travel
6. **✅ ML Pipeline**: Feature engineering (Silver) và model training với 99%+ accuracy
7. **✅ MLflow Integration**: ML experiment tracking và model registry (coming soon)

**Kiểm tra hoạt động:**

- **Kafka Producer**: `docker logs data-producer` - data được publish liên tục
- **Spark Streaming**: Batch processing messages hiển thị "Batch X written to Bronze successfully"
- **MinIO Storage**: Parquet files xuất hiện trong `lakehouse/bronze/transactions/`
- **Delta Lake**: Transaction logs trong `_delta_log/` folder
- **Silver Layer**: 42 features được tạo cho fraud detection
- **ML Training**: Random Forest đạt 99.99% AUC, 83.33% fraud detection rate

### 10. Tiếp theo

Sau khi Data Lakehouse và ML Pipeline hoạt động ổn định, các bước phát triển tiếp theo:

- ✅ **Machine Learning Pipeline**: Hoàn thành với 99%+ accuracy fraud detection
- 🔧 **MLflow Integration**: Setup tracking server và model registry
- 📊 **Analytics Dashboard**: Metabase cho real-time fraud monitoring
- 🤖 **AI Chatbot**: LangChain + OpenAI để intelligent querying
- 🔄 **Workflow Orchestration**: Airflow cho automated model retraining
- 🚀 **Model Serving**: FastAPI service cho real-time prediction
- 🎯 **Real-time Scoring**: Integrate model với streaming pipeline

### 11. Cấu trúc dữ liệu Lakehouse

```
s3a://lakehouse/
├── bronze/           # Raw data từ Kafka
│   └── transactions/
│       └── year=2025/month=11/day=9/  # Partitioned by date
├── silver/           # Cleaned & enriched data với 42 features
│   ├── transactions/
│   └── features/     # ML-ready feature sets
├── gold/             # Aggregated analytics data
│   ├── aggregated/
│   └── reports/      # Fraud summary reports
├── checkpoints/      # Spark streaming checkpoints
│   ├── bronze/
│   ├── silver/
│   └── gold/
└── models/           # ML models và artifacts
    ├── fraud_detection/
    └── experiments/
```

### 12. ML Pipeline Performance

**Feature Engineering (Silver Layer):**

- 🔢 **42 Features** được tạo từ raw transaction data
- 📊 **Statistical Features**: log_amount, amount_ranges, rolling averages
- ⏰ **Time Features**: hour_sin, hour_cos, time-based patterns
- 🔗 **Interaction Features**: V1-V2 combinations, cross-features
- ✅ **Data Quality**: 6610 valid transactions, 99.21% normal, 0.79% fraud

**Model Performance Comparison:**

| Model                   | AUC    | Accuracy | Precision | Recall | F1-Score | Fraud Detection Rate |
| ----------------------- | ------ | -------- | --------- | ------ | -------- | -------------------- |
| **Random Forest**       | 99.99% | 99.76%   | 99.76%    | 99.76% | 99.76%   | **83.33%** ⭐        |
| **Logistic Regression** | 99.93% | 99.53%   | 99.50%    | 99.53% | 99.51%   | 66.67%               |

**🏆 Random Forest** được chọn làm model chính với:

- Fraud detection rate cao nhất: **83.33%**
- AUC gần hoàn hảo: **99.99%**
- Balanced performance across all metrics
- Suitable cho production fraud detection system

### 13. Production Readiness

**✅ Đã hoàn thành:**

- Data ingestion pipeline với Kafka
- Lakehouse architecture với Bronze/Silver/Gold layers
- Feature engineering với 42 fraud-specific features
- ML training pipeline với model comparison
- High-performance fraud detection (83.33% detection rate)

**🔧 Đang phát triển:**

- MLflow model registry và experiment tracking
- Real-time model serving với FastAPI
- Fraud monitoring dashboard với Metabase
- AI chatbot cho fraud investigation

**📈 Metrics để monitor:**

- **Latency**: Streaming processing < 10s per batch
- **Accuracy**: Model performance > 99% AUC
- **Detection Rate**: Fraud catching rate > 80%
- **Throughput**: Process 1000+ transactions/minute

---

## 🔧 Troubleshooting

### Common Issues

**1. MLflow Connection Issues:**

```bash
# Check MLflow service
docker logs realtime-fraud-detection-lakehouse-mlflow-1

# Restart MLflow service
docker-compose restart mlflow
```

**2. Dependency Conflicts:**

- `urllib3` version conflicts are **warnings only** - không ảnh hưởng functionality
- Spark containers sử dụng isolated environments
- Production deployment sẽ có fixed dependency versions

**3. Memory Issues:**

```bash
# Increase Docker memory limit
# Docker Desktop > Settings > Resources > Memory: 8GB+

# Monitor Spark resource usage
docker exec spark-master spark-submit --help
```

**4. Delta Lake Issues:**

```bash
# Clear Delta checkpoints nếu có lỗi
docker exec spark-master rm -rf /opt/spark/work-dir/checkpoints/*

# Restart streaming jobs
docker-compose restart spark-master spark-worker
```

---

## 🚀 Next Steps

### Phase 1: Model Deployment

- [ ] Fix MLflow connectivity cho model registry
- [ ] Deploy Random Forest model to production
- [ ] Create FastAPI endpoint cho real-time fraud scoring
- [ ] Implement model A/B testing framework

### Phase 2: Analytics Dashboard

- [ ] Test Gold layer aggregation pipeline
- [ ] Configure Metabase với Trino connection
- [ ] Create fraud monitoring dashboards
- [ ] Setup alerting cho high-risk transactions

### Phase 3: AI Chatbot

- [ ] Implement LangChain fraud investigation chatbot
- [ ] Connect với Trino query engine
- [ ] Deploy Streamlit interface
- [ ] Add natural language fraud pattern analysis

### Phase 4: Production Optimization

- [ ] Scale Kafka cluster cho high throughput
- [ ] Optimize Spark streaming performance
- [ ] Implement data quality monitoring
- [ ] Add comprehensive logging và monitoring

---

## 📊 Architecture Verification

**✅ Verified Components:**

- ✅ Kafka: Streaming data ingestion
- ✅ Spark: Bronze/Silver layer processing
- ✅ Delta Lake: ACID transactions
- ✅ MinIO: S3-compatible storage
- ✅ PostgreSQL: Metadata storage
- ✅ ML Pipeline: 99%+ accuracy fraud detection

**🔧 In Progress:**

- 🔄 MLflow: Model tracking (infrastructure ready)
- 🔄 Gold Layer: Analytics aggregation (code ready)
- 🔄 Trino: Query engine (configured)
- 🔄 Metabase: Dashboard (waiting for data)

**📅 Roadmap:**

- Week 1: Complete MLflow integration + Gold layer testing
- Week 2: Deploy fraud detection API + dashboards
- Week 3: Implement AI chatbot + production optimization
- Week 4: Performance tuning + monitoring setup
