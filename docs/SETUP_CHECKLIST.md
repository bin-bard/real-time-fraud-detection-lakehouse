# Setup Checklist - Fraud Detection Lakehouse

Checklist này giúp verify rằng hệ thống được setup đầy đủ khi clone repo mới.

## ✅ Pre-Setup

- [ ] Docker Desktop installed (Windows/Mac) hoặc Docker Engine (Linux)
- [ ] Docker Compose 2.0+
- [ ] Cấu hình RAM: Min 10GB, Recommended 16GB
- [ ] Disk space: 30GB free
- [ ] (Optional) Gemini API key nếu dùng Chatbot

## ✅ Step 1: Clone & Configure

```bash
git clone https://github.com/bin-bard/real-time-fraud-detection-lakehouse.git
cd real-time-fraud-detection-lakehouse
```

**Tạo file `.env`:**

```bash
# Copy từ template
cp .env.example .env

# Sửa GOOGLE_API_KEY nếu dùng chatbot
nano .env  # hoặc notepad .env (Windows)
```

## ✅ Step 2: Start Services

```bash
docker compose up -d --build
```

**Wait 5-10 minutes** cho services khởi động.

**✅ Database tự động khởi tạo:**

- PostgreSQL tự động chạy `database/init_postgres.sql` khi container khởi động lần đầu
- Tất cả tables, indexes, constraints, và comments được tạo sẵn
- Không cần chạy migration thủ công!

**Verify services:**

```bash
docker ps --format "table {{.Names}}\t{{.Status}}"
```

Expected: ~15 containers running (postgres, minio, mlflow, trino, airflow, chatbot, etc.)

**Verify database schema:**

```bash
docker exec postgres psql -U postgres -d frauddb -c "\d fraud_predictions"
```

**Expected:**

- ✅ `fraud_predictions_trans_num_key` UNIQUE constraint
- ✅ `fraud_predictions_trans_num_fkey` FOREIGN KEY constraint
- ✅ Indexes: `idx_fraud_predictions_time`, `idx_fraud_predictions_model_version`

## ✅ Step 3: Load Data

```bash
# Bulk load 50K transactions
docker exec data-producer python producer.py --bulk-load 50000
```

**Wait 2-3 minutes**

**Verify data:**

```bash
docker exec postgres psql -U postgres -d frauddb -c "SELECT COUNT(*) FROM transactions;"
```

Expected: ~50,000 rows

## ✅ Step 5: Wait for Spark Jobs

Bronze → Silver → Gold jobs chạy mỗi 5 phút (Airflow).

**Check Airflow:**

- URL: http://localhost:8081
- Username: `airflow`
- Password: `airflow`

**Wait for DAGs:**

- `lakehouse_pipeline_taskflow` - Should run within 5 minutes
- Check logs cho Bronze/Silver/Gold tasks

**Verify Delta Lake:**

```bash
# Check Trino
docker exec trino trino --execute "SELECT COUNT(*) FROM delta.gold.fact_transactions;"
```

Expected: ~50,000 rows (sau khi pipeline chạy xong)

## ✅ Step 4: Train ML Model

**Option 1: Manual trigger (Fast)**

```bash
# Trigger Airflow DAG
curl -X POST http://localhost:8081/api/v1/dags/model_retraining_taskflow/dagRuns \
  -H "Content-Type: application/json" \
  -u airflow:airflow \
  -d '{"conf":{}}'
```

**Option 2: Wait for scheduled run (2 AM daily)**

**Verify model:**

- MLflow: http://localhost:5001
- Check "sklearn_fraud_randomforest" model
- Should have "Production" version

**Test API:**

```bash
curl http://localhost:8000/health
```

Expected:

```json
{
  "status": "healthy",
  "model_loaded": true,
  "model_version": "v2"
}
```

## ✅ Step 5: Test Chatbot (Optional)

**Restart chatbot để load model:**

```bash
docker compose restart fraud-chatbot
```

**Access chatbot:**

- URL: http://localhost:8501

**Test queries:**

1. "Thông tin model" → Should show model metrics
2. "Top 5 bang có fraud rate cao nhất" → Should query Trino
3. "Dự đoán giao dịch $850 lúc 2h sáng" → Should call prediction API

**Verify chatbot logs:**

```bash
docker logs fraud-chatbot --tail 50
```

Expected: No errors, agent should execute successfully

## ✅ Step 6: Access Dashboards

| Service   | URL                   | Credentials          |
| --------- | --------------------- | -------------------- |
| Airflow   | http://localhost:8081 | airflow / airflow    |
| MLflow    | http://localhost:5001 | (no auth)            |
| MinIO     | http://localhost:9001 | minio / minio123     |
| Chatbot   | http://localhost:8501 | (no auth)            |
| Fraud API | http://localhost:8000 | (no auth)            |
| Trino     | http://localhost:8085 | (no auth)            |
| Metabase  | http://localhost:3000 | (setup on first run) |

## ⚠️ Troubleshooting

### Services không start

```bash
# Check logs
docker compose logs <service-name>

# Common issues:
# - RAM không đủ → Tăng Docker RAM limit
# - Port conflict → Sửa docker-compose.yml
```

### Database schema issues

```bash
# Verify schema được tạo đúng
docker exec postgres psql -U postgres -d frauddb -c "\d"

# Nếu thiếu tables, rebuild postgres container
docker compose down postgres
docker volume rm real-time-fraud-detection-lakehouse_postgres_data
docker compose up -d postgres
```

### Spark jobs failed

```bash
# Check Airflow logs
docker logs airflow-scheduler

# Common issues:
# - MinIO không connect → Check MinIO service
# - Memory OOM → Tăng RAM
```

### Chatbot errors

```bash
# Check API health
curl http://localhost:8000/health

# Check Gemini API key
docker exec fraud-chatbot env | grep GOOGLE_API_KEY

# Rebuild chatbot
docker compose up -d --build fraud-chatbot
```

## 🎯 Success Criteria

Hệ thống setup thành công khi:

- ✅ All 15 containers running
- ✅ Database schema tự động khởi tạo (fraud_predictions có foreign key)
- ✅ 50K+ transactions in PostgreSQL
- ✅ Delta Lake có data trong Gold layer
- ✅ ML model trained và có version "Production" trong MLflow
- ✅ Fraud Detection API trả về `model_loaded: true`
- ✅ Chatbot trả lời được câu hỏi về model và data
- ✅ Airflow DAGs chạy thành công

## 📝 Reset Hệ Thống

Nếu cần reset hoàn toàn:

```bash
# Stop và xóa tất cả volumes
docker compose down -v

# Xóa Delta Lake data (nếu cần)
rm -rf spark/warehouse/*

# Start lại - Database sẽ tự động init
docker compose up -d --build

# Load data
docker exec data-producer python producer.py --bulk-load 50000
```

**Lưu ý:** Không cần chạy migration thủ công - `init_postgres.sql` tự động chạy khi container postgres khởi động lần đầu!

## 🚀 Next Steps

Sau khi setup xong:

1. **Explore Chatbot** - Chat với data bằng tiếng Việt
2. **View Airflow** - Xem pipeline ETL và ML training
3. **Check MLflow** - Theo dõi model performance
4. **Query Trino** - Chạy SQL phân tích trên Delta Lake
5. **Setup Metabase** - Tạo dashboard BI

## 📚 Documentation

- [README.md](../README.md) - Overview
- [SETUP_GUIDE.md](SETUP_GUIDE.md) - Chi tiết setup
- [CHATBOT_GUIDE.md](CHATBOT_GUIDE.md) - Hướng dẫn chatbot
- [REALTIME_ARCHITECTURE.md](REALTIME_ARCHITECTURE.md) - Kiến trúc real-time
