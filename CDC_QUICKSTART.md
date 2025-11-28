# Quick Start Guide - CDC Pipeline

## Tổng quan luồng dữ liệu mới

```
CSV → PostgreSQL → Debezium CDC → Kafka → Spark Streaming → Data Lakehouse
```

## Các bước khởi động nhanh

### 1. Khởi động infrastructure

```bash
docker-compose up -d
```

Đợi 30-60 giây để tất cả services sẵn sàng.

### 2. Load dữ liệu ban đầu vào PostgreSQL

```bash
docker-compose --profile setup up data-loader
```

Hoặc:

```bash
docker-compose run --rm data-loader
```

### 3. Đăng ký Debezium CDC Connector

**Windows (PowerShell):**
```powershell
cd scripts
.\setup_cdc_pipeline.ps1
```

**Linux/Mac:**
```bash
cd scripts
chmod +x setup_cdc_pipeline.sh
./setup_cdc_pipeline.sh
```

### 4. Kiểm tra CDC hoạt động

```bash
# Kiểm tra topics trong Kafka
docker exec -it kafka kafka-topics --bootstrap-server localhost:9092 --list

# Xem CDC messages
docker exec -it kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic dbserver1.public.transactions \
  --from-beginning
```

### 5. Khởi động Spark Streaming

```bash
docker exec spark-master /opt/spark/bin/spark-submit \
  --master spark://spark-master:7077 \
  --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0,io.delta:delta-core_2.12:2.4.0,org.apache.hadoop:hadoop-aws:3.3.4 \
  /app/streaming_job.py
```

### 6. Chạy real-time producer

```bash
docker-compose up data-producer
```

## Kiến trúc CDC

- **PostgreSQL**: Lưu trữ transactions với logical replication
- **Debezium**: Capture changes từ PostgreSQL WAL
- **Kafka**: Streaming platform cho CDC events
- **Kafka Topic**: `dbserver1.public.transactions`
- **Spark**: Xử lý real-time CDC events và lưu vào Lakehouse

## Services & Ports

| Service | Port | URL |
|---------|------|-----|
| PostgreSQL | 5432 | `localhost:5432` |
| Kafka | 9092 | `localhost:9092` |
| Kafka Connect | 8083 | `http://localhost:8083` |
| Spark Master UI | 8080 | `http://localhost:8080` |
| MinIO Console | 9001 | `http://localhost:9001` |

## Troubleshooting

Xem chi tiết trong: [docs/CDC_SETUP_GUIDE.md](docs/CDC_SETUP_GUIDE.md)

## Lợi ích của CDC Pipeline

1. **Tách biệt concerns**: Database không bị ảnh hưởng bởi Kafka
2. **Dữ liệu đáng tin cậy**: PostgreSQL đảm bảo ACID
3. **Capture mọi thay đổi**: INSERT, UPDATE, DELETE đều được track
4. **Dễ debug**: Có thể query trực tiếp trong PostgreSQL
5. **Scalable**: CDC không ảnh hưởng performance của database
