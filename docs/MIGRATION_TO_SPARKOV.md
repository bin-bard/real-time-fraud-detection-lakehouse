# Migration Guide: PCA Dataset → Sparkov Dataset

## Tổng quan

Tài liệu này mô tả chi tiết quá trình chuyển đổi hệ thống từ **Credit Card Fraud Detection (PCA Dataset)** sang **Sparkov Credit Card Transactions Dataset**.

---

## 1. Thay đổi Dataset

### Old Dataset (PCA)

- **File:** `creditcard.csv`
- **Rows:** ~284,807 transactions
- **Features:** 30 columns (Time, V1-V28 PCA components, Amount, Class)
- **Characteristics:** Anonymous PCA-transformed features, no semantic meaning

### New Dataset (Sparkov)

- **Files:**
  - `fraudTrain.csv` - 1,296,675 transactions (2019-2020)
  - `fraudTest.csv` - 555,719 transactions
- **Features:** 22 columns with full semantic information
- **Characteristics:**
  - Geographic data (lat/long for customer & merchant)
  - Demographic data (age, gender, job)
  - Transaction metadata (merchant, category)
  - Real-world transaction patterns

---

## 2. Schema Changes

### Bronze Layer Schema

**Old (PCA):**

```python
StructField("Time", DoubleType())
StructField("V1", DoubleType())
...
StructField("V28", DoubleType())
StructField("Amount", DoubleType())
StructField("Class", DoubleType())
```

**New (Sparkov):**

```python
StructField("trans_date_trans_time", StringType())
StructField("cc_num", StringType())
StructField("merchant", StringType())
StructField("category", StringType())
StructField("amt", DoubleType())
StructField("first", StringType())
StructField("last", StringType())
StructField("gender", StringType())
StructField("lat", DoubleType())
StructField("long", DoubleType())
StructField("merch_lat", DoubleType())
StructField("merch_long", DoubleType())
StructField("is_fraud", StringType())
# ... và 9 columns khác
```

---

## 3. Feature Engineering Changes

### Old Features (PCA-based)

```python
features = [
    "Time", "Amount",
    "V1", "V2", ..., "V28",
    "log_amount",
    "amount_v1_ratio",
    "v1_v2_interaction"
]
```

### New Features (Sparkov-based)

**Geographic Features:**

```python
# Haversine distance calculation
distance_km = haversine(lat, long, merch_lat, merch_long)
is_distant_transaction = (distance_km > 100)
```

**Demographic Features:**

```python
age = floor(datediff(current_date, dob) / 365.25)
gender_encoded = 1 if gender == 'M' else 0
```

**Time Features:**

```python
hour = hour(trans_timestamp)
day_of_week = dayofweek(trans_timestamp)
is_weekend = (day_of_week in [1, 7])
is_late_night = (hour >= 23 or hour <= 5)
hour_sin = sin(hour * 2π / 24)
hour_cos = cos(hour * 2π / 24)
```

**Amount Features:**

```python
log_amount = log(amt + 1)
amount_bin = categorize(amt)  # 0-5 bins
is_zero_amount = (amt == 0)
is_high_amount = (amt > 500)
```

**Total:** 15 engineered features

---

## 4. Code Changes Summary

### 4.1 Data Producer (`services/data-producer/producer.py`)

**Changes:**

- ❌ Removed: Kafka producer
- ✅ Added: PostgreSQL connection
- ✅ Updated: Read `fraudTrain.csv` instead of `creditcard.csv`
- ✅ Updated: INSERT statements with 22 columns

**Key Code:**

```python
# Old: Kafka producer
producer.send(KAFKA_TOPIC, value=row_data)

# New: PostgreSQL insert
cursor.execute(INSERT_QUERY, (
    trans_date_trans_time, cc_num, merchant, ...
))
```

### 4.2 Streaming Job (`spark/app/streaming_job.py`)

**Changes:**

- ✅ Updated: Kafka topic to `postgres.public.transactions` (Debezium CDC)
- ✅ Updated: Schema definition (22 fields)
- ✅ Added: Debezium payload parsing
- ✅ Added: Timestamp conversion

**Key Code:**

```python
# Parse Debezium CDC format
transaction_df = kafka_stream_df \
    .select(get_json_object(col("json_string"), "$.payload.after")) \
    .select(from_json(col("payload"), schema).alias("data"))
```

### 4.3 Silver Layer (`spark/app/silver_layer_job.py`)

**Changes:**

- ✅ Added: `haversine_distance()` function
- ✅ Updated: Feature engineering logic
- ✅ Updated: Data quality checks (new column names)
- ✅ Updated: Statistics calculation (`is_fraud` instead of `Class`)

**Key Functions:**

```python
def haversine_distance(lat1, lon1, lat2, lon2):
    # Haversine formula implementation
    ...

def feature_engineering(df):
    # 15 new features
    ...
```

### 4.4 Gold Layer (`spark/app/gold_layer_job.py`)

**Changes:**

- ✅ Updated: All aggregations to use new columns (`amt`, `is_fraud`)
- ✅ Added: Geographic analysis (by state)
- ✅ Added: Category analysis
- ✅ Added: Distance metrics in summaries

**New Aggregations:**

```python
# State-level fraud analysis
state_summary = df.groupBy("state").agg(
    count("*"),
    sum(when(col("is_fraud") == "1", 1)),
    avg("distance_km")
)

# Category fraud patterns
category_summary = df.groupBy("category").agg(...)
```

### 4.5 ML Training (`spark/app/ml_training_job.py`)

**Changes:**

- ✅ Updated: Feature selection (15 Sparkov features)
- ✅ Added: Class balancing (undersampling normal transactions)
- ✅ Updated: Model hyperparameters
- ✅ Updated: Cast `is_fraud` to integer

**Key Code:**

```python
# Feature selection
feature_cols = [
    "amt", "log_amount", "distance_km", "age",
    "hour", "day_of_week", "is_weekend", ...
]

# Class balancing
sample_ratio = min(1.0, (fraud_count * 3) / normal_count)
normal_sampled = normal_df.sample(fraction=sample_ratio)
```

### 4.6 FastAPI (`services/fraud-detection-api/app/main.py`)

**Changes:**

- ✅ Added: `TransactionFeatures` Pydantic model
- ✅ Added: `/predict` endpoint with 15 features
- ✅ Added: Rule-based prediction (temporary)
- ✅ Added: Risk level classification

**API Schema:**

```python
class TransactionFeatures(BaseModel):
    amt: float
    distance_km: float
    age: int
    hour: int
    # ... 11 more features
```

### 4.7 PostgreSQL (`scripts/init_postgres.sql`)

**Changes:**

- ✅ Created: `transactions` table with 22 columns
- ✅ Added: Indexes for performance
- ✅ Added: `fraud_predictions` table for ML results

---

## 5. Architecture Flow Changes

### Old Flow (PCA)

```
CSV → Kafka → Spark Bronze → Silver (PCA features) → Gold
```

### New Flow (Sparkov)

```
CSV → PostgreSQL → Debezium → Kafka → Spark Bronze →
  Silver (Geographic + Demographic features) → Gold
```

**Key Addition:** Debezium CDC layer for real-time change capture

---

## 6. Performance Considerations

### Data Volume

- **Old:** ~285K transactions
- **New:** ~1.3M transactions (4.6x larger)
- **Impact:** Longer processing time, more partitions needed

### Feature Complexity

- **Old:** Simple PCA features (already normalized)
- **New:** Complex calculations (Haversine, date math, trigonometry)
- **Impact:** More CPU-intensive transformations

### Recommendations

1. **Partitioning:** Use `year/month/day` for better data locality
2. **Caching:** Cache Silver layer for iterative ML training
3. **Sampling:** Use stratified sampling for development/testing
4. **Indexing:** PostgreSQL indexes on `trans_date_trans_time`, `cc_num`, `is_fraud`

---

## 7. Testing Checklist

### Data Pipeline

- [ ] Producer successfully inserts to PostgreSQL
- [ ] Debezium captures INSERT events to Kafka
- [ ] Spark reads CDC events and writes to Bronze
- [ ] Silver layer creates all 15 features correctly
- [ ] Gold layer aggregations complete without errors

### Feature Engineering

- [ ] `distance_km` calculated correctly (Haversine)
- [ ] `age` calculated from `dob`
- [ ] Time features (hour, day_of_week) extracted
- [ ] Cyclic encoding (sin/cos) working
- [ ] All features non-null for valid transactions

### ML Pipeline

- [ ] Model trains on Sparkov features
- [ ] Class balancing working correctly
- [ ] Model achieves >80% fraud detection rate
- [ ] MLflow logs experiments properly

### API

- [ ] `/predict` accepts 15 features
- [ ] Returns valid predictions
- [ ] Risk level classification works
- [ ] API handles missing features gracefully

---

## 8. Migration Steps for Production

### Step 1: Data Preparation

```bash
# Download Sparkov dataset
# Place fraudTrain.csv in data/ folder
cp path/to/fraudTrain.csv data/
```

### Step 2: Database Setup

```bash
# Run new PostgreSQL schema
docker exec -i postgres psql -U postgres < scripts/init_postgres.sql
```

### Step 3: Update Dependencies

```bash
# Producer
pip install psycopg2-binary python-dateutil

# API
pip install pydantic numpy mlflow
```

### Step 4: Deploy Services

```bash
# Restart all services with new code
docker-compose down
docker-compose up -d

# Verify connections
docker logs data-producer
docker logs spark-master
```

### Step 5: Validate Pipeline

```bash
# Check Bronze layer
docker exec spark-master spark-submit /app/streaming_job.py

# Check Silver layer
docker exec spark-master spark-submit /app/silver_layer_job.py

# Check Gold layer
docker exec spark-master spark-submit /app/gold_layer_job.py
```

### Step 6: Train Initial Model

```bash
docker exec spark-master spark-submit /app/ml_training_job.py
```

---

## 9. Rollback Plan

If issues occur, rollback to PCA dataset:

1. **Stop all services:** `docker-compose down`
2. **Checkout previous commit:** `git checkout <previous-commit>`
3. **Replace data file:** Copy `creditcard.csv` back to `data/`
4. **Restart:** `docker-compose up -d`

**Estimated rollback time:** 10-15 minutes

---

## 10. Known Issues & Limitations

### Current Limitations

1. **Debezium:** Not yet configured in docker-compose (manual setup required)
2. **MLflow:** Model registry integration pending
3. **API:** Using rule-based prediction (ML model loading TODO)
4. **Monitoring:** No dashboards/chatbot yet

### Future Enhancements

1. Add Debezium connector configuration
2. Implement real-time model serving
3. Add feature store for consistency
4. Implement data quality monitoring
5. Add A/B testing for models

---

## 11. Contact & Support

**For questions about this migration:**

- Check `docs/PROJECT_SPECIFICATION.md` for architecture details
- Review code comments in updated files
- See README.md for setup instructions

**Key Files Changed:**

- `services/data-producer/producer.py`
- `spark/app/streaming_job.py`
- `spark/app/silver_layer_job.py`
- `spark/app/gold_layer_job.py`
- `spark/app/ml_training_job.py`
- `services/fraud-detection-api/app/main.py`
- `scripts/init_postgres.sql`

---

**Migration Completed:** ✅  
**Version:** 2.0.0  
**Date:** November 2024  
**Status:** Ready for testing
