# CDC Setup Guide - PostgreSQL + Debezium + Kafka

Hướng dẫn thiết lập Change Data Capture (CDC) pipeline với PostgreSQL, Debezium và Kafka.

## Kiến trúc mới

**Luồng dữ liệu:** CSV → PostgreSQL → CDC (Debezium) → Kafka → Spark Streaming → Data Lakehouse

### Các thành phần:

1. **PostgreSQL**: Database lưu trữ transactions
2. **Debezium Connect**: Capture changes từ PostgreSQL
3. **Kafka**: Message broker nhận CDC events
4. **Spark Streaming**: Xử lý real-time data từ Kafka
5. **MinIO**: Data Lake storage

---

## Bước 1: Khởi động các services

```bash
# Khởi động tất cả services
docker-compose up -d

# Kiểm tra services đang chạy
docker-compose ps
```

Đợi khoảng 30-60 giây để tất cả services khởi động hoàn tất.

---

## Bước 2: Load dữ liệu CSV vào PostgreSQL (Initial Load)

```bash
# Chạy data-loader để load CSV vào PostgreSQL
docker-compose --profile setup up data-loader

# Hoặc build và chạy riêng
docker-compose build data-loader
docker-compose run --rm data-loader
```

Script này sẽ:
- Đợi PostgreSQL sẵn sàng
- Đọc file `creditcard.csv`
- Insert toàn bộ dữ liệu vào table `public.transactions`
- Chỉ load nếu table còn trống (tránh duplicate)

---

## Bước 3: Đăng ký Debezium Connector

### Windows (PowerShell):

```powershell
cd scripts
.\setup_cdc_pipeline.ps1
```

### Linux/Mac:

```bash
cd scripts
chmod +x setup_cdc_pipeline.sh
./setup_cdc_pipeline.sh
```

Script này sẽ:
1. Đợi Kafka Connect sẵn sàng
2. Đăng ký PostgreSQL connector với Debezium
3. Kiểm tra trạng thái connector

### Kiểm tra connector thủ công:

```bash
# Liệt kê các connectors
curl http://localhost:8083/connectors

# Xem chi tiết connector
curl http://localhost:8083/connectors/postgres-transactions-connector/status

# Xóa connector (nếu cần)
curl -X DELETE http://localhost:8083/connectors/postgres-transactions-connector
```

---

## Bước 4: Xác minh CDC hoạt động

### Kiểm tra Kafka topics:

```bash
# Vào Kafka container
docker exec -it kafka bash

# Liệt kê topics
kafka-topics --bootstrap-server localhost:9092 --list

# Đọc messages từ CDC topic
kafka-console-consumer --bootstrap-server localhost:9092 \
  --topic dbserver1.public.transactions \
  --from-beginning
```

Bạn sẽ thấy messages với format:

```json
{
  "id": 1,
  "time_seconds": 0.0,
  "v1": -1.3598071336738,
  "amount": 149.62,
  "class": 0,
  "created_at": 1732780800000,
  "updated_at": 1732780800000
}
```

---

## Bước 5: Chạy Spark Streaming để xử lý CDC data

```bash
# Submit Spark job
docker exec spark-master /opt/spark/bin/spark-submit \
  --master spark://spark-master:7077 \
  --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0,io.delta:delta-core_2.12:2.4.0,org.apache.hadoop:hadoop-aws:3.3.4 \
  /app/streaming_job.py
```

---

## Bước 6: Streaming real-time transactions

Sau khi setup xong, chạy data-producer để insert real-time transactions:

```bash
docker-compose up data-producer
```

Producer sẽ:
1. Đọc từng dòng từ CSV
2. Insert vào PostgreSQL với delay giữa các transactions
3. Debezium tự động capture changes
4. CDC events được gửi vào Kafka
5. Spark Streaming xử lý real-time

---

## Cấu trúc Database

### Table: `public.transactions`

```sql
CREATE TABLE public.transactions (
    id SERIAL PRIMARY KEY,
    time_seconds DOUBLE PRECISION NOT NULL,
    v1 DOUBLE PRECISION,
    v2 DOUBLE PRECISION,
    ...
    v28 DOUBLE PRECISION,
    amount DOUBLE PRECISION NOT NULL,
    class INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## Debezium Configuration

### Topic name pattern:
`<topic.prefix>.<schema>.<table>`

Ví dụ: `dbserver1.public.transactions`

### Connector config:
- **plugin.name**: pgoutput (PostgreSQL native logical replication)
- **snapshot.mode**: initial (capture existing data + new changes)
- **transforms**: ExtractNewRecordState (chỉ lấy phần 'after' của CDC event)

---

## Troubleshooting

### 1. Kafka Connect không khởi động

```bash
# Xem logs
docker logs kafka-connect

# Kiểm tra health
curl http://localhost:8083/
```

### 2. Connector lỗi

```bash
# Xem connector status
curl http://localhost:8083/connectors/postgres-transactions-connector/status

# Restart connector
curl -X POST http://localhost:8083/connectors/postgres-transactions-connector/restart
```

### 3. PostgreSQL WAL không hoạt động

```bash
# Kiểm tra wal_level
docker exec postgres-db psql -U postgres -d transactions -c "SHOW wal_level;"

# Phải là 'logical'
```

### 4. Không thấy messages trong Kafka

```bash
# Kiểm tra replication slot
docker exec postgres-db psql -U postgres -d transactions \
  -c "SELECT * FROM pg_replication_slots;"

# Kiểm tra publication
docker exec postgres-db psql -U postgres -d transactions \
  -c "SELECT * FROM pg_publication;"
```

---

## Ports

- PostgreSQL: `5432`
- Kafka Connect: `8083`
- Kafka: `9092`
- Spark Master UI: `8080`
- MinIO Console: `9001`

---

## Next Steps

1. Implement ML fraud detection trong Spark Streaming
2. Setup alerting cho fraud transactions
3. Configure Metabase dashboards
4. Implement model retraining pipeline

---

## References

- [Debezium PostgreSQL Connector](https://debezium.io/documentation/reference/stable/connectors/postgresql.html)
- [Kafka Connect REST API](https://docs.confluent.io/platform/current/connect/references/restapi.html)
- [PostgreSQL Logical Replication](https://www.postgresql.org/docs/current/logical-replication.html)
