#!/bin/bash
# Script tạo bucket manual trong MinIO

echo "🚀 Creating MinIO bucket manually..."

# Đợi MinIO khởi động
sleep 10

# Tạo bucket bằng MinIO client (mc)
docker exec -i minio mc config host add local http://localhost:9000 minio minio123
docker exec -i minio mc mb local/lakehouse
docker exec -i minio mc ls local

echo "✅ Bucket 'lakehouse' created successfully!"