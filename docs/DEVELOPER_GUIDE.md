# Developer Guide - Hướng dẫn phát triển

Tài liệu dành cho developers muốn phát triển, maintain, hoặc mở rộng hệ thống.

---

## Mục lục

1. [Development Setup](#1-development-setup)
2. [Code Organization](#2-code-organization)
3. [Key Implementations](#3-key-implementations)
4. [Performance Optimization](#4-performance-optimization)
5. [Troubleshooting & Bug Fixes](#5-troubleshooting--bug-fixes)
6. [FAQ](#6-faq)
7. [Common Operations](#7-common-operations)
8. [Testing](#8-testing)

---

## 1. Development Setup

### 1.1. Local Development Environment

**Requirements:**

- Python 3.9+
- Docker Desktop
- Git
- VS Code (recommended) với extensions:
  - Python
  - Docker
  - Jupyter

**Clone và setup:**

```bash
git clone https://github.com/bin-bard/real-time-fraud-detection-lakehouse.git
cd real-time-fraud-detection-lakehouse
```

### 1.2. Hot Reload Configuration

**Chatbot local development:**

```bash
cd services/fraud-chatbot
python -m venv venv
source venv/bin/activate  # Linux/Mac
# hoặc
venv\Scripts\activate  # Windows

pip install -r requirements.txt

# Run với hot reload
streamlit run src/main.py --server.runOnSave true
```

**API local development:**

```bash
cd services/fraud-detection-api
pip install -r requirements.txt

# Run với hot reload
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 1.3. Debugging Tips

**Debug Spark jobs:**

```bash
# Add .master("local[*]") for local debugging
spark = SparkSession.builder \
    .appName("DebugJob") \
    .master("local[*]") \
    .config("spark.ui.enabled", "true") \
    .config("spark.ui.port", "4040") \
    .getOrCreate()

# Access Spark UI: http://localhost:4040
```

**Debug Streamlit:**

```python
# Add logging
import logging
logging.basicConfig(level=logging.DEBUG)

# Use st.write() for quick inspection
st.write("DEBUG:", variable_name)

# Use st.expander() for detailed logs
with st.expander("Debug Info"):
    st.json(debug_data)
```

**Debug FastAPI:**

```python
# Add print statements (visible in docker logs)
print(f"DEBUG: Received data: {data}")

# Use logging
import logging
logger = logging.getLogger(__name__)
logger.debug(f"Processing: {trans_num}")
```

---

## 2. Code Organization

### 2.1. Monolithic → Modular Refactoring

**Before (Monolithic):**

```
fraud-chatbot/
├── app.py                # 1251 lines - ALL logic
└── requirements.txt
```

**After (Modular - 15 modules):**

```
fraud-chatbot/
├── src/
│   ├── main.py                  # Entry point (100 lines)
│   ├── components/              # UI Components
│   │   ├── sidebar.py           # Session management
│   │   ├── chat_bubble.py       # Message rendering
│   │   ├── forms.py             # Manual form & CSV
│   │   └── analytics_charts.py  # Plotly charts
│   ├── core/                    # Business Logic
│   │   ├── agent.py             # LangChain Agent
│   │   ├── tools.py             # Agent Tools
│   │   └── schema_loader.py     # Schema caching
│   ├── database/                # DB Connections
│   │   ├── postgres.py          # Chat history
│   │   └── trino.py             # Delta queries
│   ├── config/                  # Configuration
│   │   ├── config_loader.py     # YAML loader
│   │   ├── prompts.yaml         # Prompts
│   │   └── business_rules.yaml  # Rules
│   └── utils/                   # Utilities
│       ├── api_client.py        # FastAPI client
│       └── formatting.py        # Helpers
```

**Benefits:**

- Separation of concerns
- Easier testing
- Reusable components
- Better maintainability

### 2.2. Best Practices

**Naming conventions:**

- Functions: `snake_case`
- Classes: `PascalCase`
- Constants: `UPPER_SNAKE_CASE`
- Private methods: `_prefix_with_underscore`

**Docstrings:**

```python
def train_model(X_train, y_train, params: dict) -> MLModel:
    """
    Train fraud detection model with given parameters.

    Args:
        X_train: Training features (numpy array or DataFrame)
        y_train: Training labels (0=legit, 1=fraud)
        params: Model hyperparameters

    Returns:
        Trained model object

    Raises:
        ValueError: If data is empty or invalid
    """
    pass
```

**Error handling:**

```python
try:
    result = api_call()
except requests.ConnectionError:
    logger.error("API connection failed")
    st.error("Không thể kết nối API. Kiểm tra service.")
except Exception as e:
    logger.exception("Unexpected error")
    st.error(f"Lỗi: {str(e)}")
```

---

## 3. Key Implementations

### 3.1. LangChain Agent Integration

**Before (keyword-based):**

```python
# Old approach: if-else keywords
if any(word in question for word in ["top", "cao nhất", "phân tích"]):
    # Execute SQL query
elif any(word in question for word in ["dự đoán", "predict"]):
    # Call prediction API
else:
    # Gemini general knowledge
```

**After (Agent-based):**

```python
# New approach: ReAct Agent
from langchain.agents import create_react_agent, AgentExecutor
from langchain_google_genai import ChatGoogleGenerativeAI

# Define tools
tools = [
    Tool(
        name="QueryDatabase",
        func=query_trino_database,
        description="Execute SQL queries on Trino Delta Lake"
    ),
    Tool(
        name="PredictFraud",
        func=call_prediction_api,
        description="Predict fraud probability for a transaction"
    )
]

# Create agent
llm = ChatGoogleGenerativeAI(model="gemini-pro", temperature=0)
agent = create_react_agent(llm, tools, prompt_template)
agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

# Execute
result = agent_executor.invoke({"input": user_question})
```

**Benefits:**

- Auto tool selection
- Multi-tool orchestration
- Complex query handling
- Better accuracy

### 3.2. Prediction API Endpoints

**FastAPI có 2 endpoints chính:**

**1. `/predict` - Full Features (deprecated for manual use)**

Yêu cầu client gửi đầy đủ 15 features đã engineer:

```python
class TransactionFeatures(BaseModel):
    amt: float
    log_amount: float
    amount_bin: int
    is_zero_amount: int
    is_high_amount: int
    distance_km: float
    is_distant_transaction: int
    age: int
    gender_encoded: int
    hour: int
    day_of_week: int
    is_weekend: int
    is_late_night: int
    hour_sin: float
    hour_cos: float
```

**2. `/predict/raw` - Raw Transaction (recommended)**

**Chatbot và manual predictions sử dụng endpoint này!**

Chỉ cần gửi raw data, API tự động tính features:

```python
class RawTransactionInput(BaseModel):
    amt: float  # Required
    hour: Optional[int] = None
    distance_km: Optional[float] = None
    age: Optional[int] = None
    gender: Optional[str] = None  # 'M' or 'F'
    day_of_week: Optional[int] = None
    trans_num: Optional[str] = None
```

API tự động:

- Tính `log_amount`, `amount_bin`, `is_high_amount`, `is_zero_amount`
- Tính `hour_sin`, `hour_cos`
- Tính `is_weekend`, `is_late_night`, `is_distant_transaction`
- Fill defaults cho missing values
- Chạy feature engineering pipeline
- Gọi ML model
- Lưu prediction vào DB (nếu là real-time transaction, không là CHAT*/MANUAL*)

### 3.3. Feature Engineering Logic

**File:** `services/fraud-detection-api/app/feature_engineering.py`

**Key functions:**

```python
def calculate_distance(lat1, lon1, lat2, lon2):
    """Haversine formula - distance in km"""
    R = 6371  # Earth radius in km
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    return R * c

def extract_time_features(datetime_obj):
    """Extract hour, day_of_week, is_weekend, is_late_night"""
    return {
        'hour': datetime_obj.hour,
        'day_of_week': datetime_obj.weekday(),
        'is_weekend': 1 if datetime_obj.weekday() >= 5 else 0,
        'is_late_night': 1 if 0 <= datetime_obj.hour <= 6 else 0,
        'hour_sin': sin(2 * pi * datetime_obj.hour / 24),
        'hour_cos': cos(2 * pi * datetime_obj.hour / 24)
    }

def categorize_amount(amt):
    """Amount binning"""
    if amt < 10: return 0
    elif amt < 50: return 1
    elif amt < 100: return 2
    elif amt < 250: return 3
    elif amt < 500: return 4
    elif amt < 1000: return 5
    else: return 6

def explain_features(features: Dict) -> str:
    """Generate rule-based explanation (NO Gemini API)"""
    explanations = []

    if features.get('is_high_amount'):
        explanations.append(f"- Giao dịch có giá trị cao (${features['amt']:.2f})")

    if features.get('is_distant_transaction'):
        explanations.append(f"- Giao dịch xa {features['distance_km']:.1f}km từ địa chỉ khách hàng")

    if features.get('is_late_night'):
        explanations.append(f"- Giao dịch vào lúc {features['hour']}h (đêm khuya/sáng sớm)")

    if features.get('is_weekend'):
        explanations.append("- Giao dịch vào cuối tuần")

    return "\n".join(explanations) if explanations else "Không có đặc điểm bất thường nổi bật"
```

**Lưu ý:** `explain_features()` là **rule-based** (không dùng Gemini API) để đảm bảo tốc độ real-time.

### 3.3. Dynamic Schema Loader với Caching

**File:** `services/fraud-chatbot/src/core/schema_loader.py`

**Implementation:**

```python
class TrinoSchemaLoader:
    def __init__(self, cache_ttl_seconds=300):
        self._cache = {}
        self._cache_timestamps = {}
        self.cache_ttl = cache_ttl_seconds

    def _is_cache_valid(self, key: str) -> bool:
        """Check if cached data hasn't expired"""
        if key not in self._cache or key not in self._cache_timestamps:
            return False

        cache_time = self._cache_timestamps[key]
        elapsed = (datetime.now() - cache_time).total_seconds()
        return elapsed < self.cache_ttl

    def _set_cache(self, key: str, value):
        """Store data with timestamp"""
        self._cache[key] = value
        self._cache_timestamps[key] = datetime.now()

    def _get_cache(self, key: str):
        """Get cached data if valid"""
        if self._is_cache_valid(key):
            return self._cache[key]
        return None

    def get_tables(self):
        """Get list of tables with caching"""
        cache_key = f"tables_{self.catalog}_{self.schema}"

        cached = self._get_cache(cache_key)
        if cached is not None:
            return cached

        # Query Trino
        query = f"SHOW TABLES FROM {self.catalog}.{self.schema}"
        result = self.conn.execute(query)
        tables = [row[0] for row in result]

        self._set_cache(cache_key, tables)
        return tables

    def format_schema_for_prompt(self):
        """Get formatted schema string with caching"""
        cache_key = "formatted_schema"

        cached = self._get_cache(cache_key)
        if cached is not None:
            return cached

        # Build schema string
        formatted = []
        for table in self.get_tables():
            columns = self.get_table_schema(table)
            formatted.append(f"{table}: {', '.join(columns)}")

        result = "\n".join(formatted)
        self._set_cache(cache_key, result)
        return result
```

**Performance Impact:**

- Cold query: 2-5 giây (query Trino)
- Warm query: < 1ms (from cache)
- **99%+ performance improvement**

**Cache keys:**

- `tables_{catalog}_{schema}`: List of tables
- `schema_{catalog}_{schema}_{table}`: Table columns
- `formatted_schema`: Full formatted string

### 3.4. YAML Config Management

**prompts.yaml:**

```yaml
system_prompt: |
  You are a fraud detection assistant for a financial institution.
  You have access to a Delta Lake database with transaction data.

  Available tools:
  1. QueryDatabase: Execute SQL queries
  2. PredictFraud: Predict fraud for a transaction

  Always provide clear, accurate responses in Vietnamese.

sql_generation_prompt: |
  Generate a SQL query for Trino to answer: {question}

  Available tables:
  {schema}

  Return ONLY the SQL query, no explanation.

prediction_prompt: |
  Analyze this fraud prediction result and provide insights:

  Amount: ${amt}
  Probability: {probability}%
  Risk Level: {risk_level}

  Explain why this transaction is risky or safe.
```

**business_rules.yaml:**

```yaml
risk_thresholds:
  low: 0.5
  medium: 0.8
  high: 1.0

high_risk_categories:
  - misc_net
  - shopping_net
  - online

amount_bins:
  - label: "Very Low"
    range: [0, 10]
  - label: "Low"
    range: [10, 50]
  - label: "Medium"
    range: [50, 100]
  - label: "High"
    range: [100, 250]
  - label: "Very High"
    range: [250, 1000]
  - label: "Extreme"
    range: [1000, null]

time_periods:
  late_night: [0, 6]
  morning: [6, 12]
  afternoon: [12, 18]
  evening: [18, 24]
```

**Loading:**

```python
import yaml

def load_config(config_file):
    with open(config_file, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

prompts = load_config('config/prompts.yaml')
rules = load_config('config/business_rules.yaml')
```

### 3.5. SQL Query Tracking Fix

**Problem:** SQL queries không được lưu vào `chat_history` table.

**Old code:**

```python
# Không lưu SQL query
save_message(session_id, "assistant", response_text)
```

**Fixed code:**

```python
# Lưu cả SQL query
save_message(
    session_id=session_id,
    role="assistant",
    message=response_text,
    sql_query=executed_query  # NEW
)
```

**Database schema update:**

```sql
ALTER TABLE chat_history
ADD COLUMN sql_query TEXT;
```

### 3.6. Fraud Predictions Storage Fix

**Problem:** Duplicate predictions gây lỗi.

**Old schema:**

```sql
CREATE TABLE fraud_predictions (
    id SERIAL PRIMARY KEY,
    trans_num VARCHAR(100),  -- NO unique constraint
    ...
);
```

**Fixed schema:**

```sql
CREATE TABLE fraud_predictions (
    id SERIAL PRIMARY KEY,
    trans_num VARCHAR(100) UNIQUE NOT NULL,  -- UNIQUE constraint
    prediction_score NUMERIC(5,4),
    is_fraud_predicted SMALLINT,
    model_version VARCHAR(50),
    prediction_time TIMESTAMP,

    CONSTRAINT fraud_predictions_trans_num_fkey
    FOREIGN KEY (trans_num) REFERENCES transactions(trans_num)
);

-- Upsert logic in code
INSERT INTO fraud_predictions (...)
ON CONFLICT (trans_num)
DO UPDATE SET
    prediction_score = EXCLUDED.prediction_score,
    is_fraud_predicted = EXCLUDED.is_fraud_predicted,
    model_version = EXCLUDED.model_version,
    prediction_time = EXCLUDED.prediction_time;
```

---

## 4. Performance Optimization

### 4.1. Schema Caching (99%+ improvement)

**Metrics:**

| Operation                    | Before | After | Improvement |
| ---------------------------- | ------ | ----- | ----------- |
| `get_tables()`               | 2-3s   | <1ms  | 99.95%      |
| `get_table_schema()`         | 1-2s   | <1ms  | 99.9%       |
| `format_schema_for_prompt()` | 5-8s   | <1ms  | 99.98%      |

**Configuration:**

- Default TTL: 300 seconds (5 minutes)
- Tunable per instance
- Manual clear via `clear_cache()`

### 4.2. Spark Configuration

**spark-defaults.conf:**

```properties
# Memory
spark.executor.memory=2g
spark.driver.memory=2g
spark.executor.memoryOverhead=512m

# Cores
spark.executor.cores=2
spark.default.parallelism=8

# Delta Lake optimization
spark.databricks.delta.optimizeWrite.enabled=true
spark.databricks.delta.autoCompact.enabled=true
spark.databricks.delta.retentionDurationCheck.enabled=false

# Shuffle
spark.sql.shuffle.partitions=200
spark.shuffle.service.enabled=true

# S3/MinIO
spark.hadoop.fs.s3a.fast.upload=true
spark.hadoop.fs.s3a.block.size=128M
spark.hadoop.fs.s3a.connection.maximum=50
```

**Tuning tips:**

- Tăng `spark.executor.memory` nếu OOM
- Giảm `spark.sql.shuffle.partitions` cho small data
- Tăng `spark.default.parallelism` cho large data

### 4.3. Resource Management

**Docker resource limits:**

```yaml
# docker-compose.yml
services:
  spark-streaming:
    deploy:
      resources:
        limits:
          cpus: "2"
          memory: 4G
        reservations:
          cpus: "1"
          memory: 2G
```

**Monitor usage:**

```bash
docker stats
```

---

## 5. Troubleshooting & Bug Fixes

### 5.1. Bug #1: Debezium NUMERIC Encoding

**Triệu chứng:** `amt` field = NULL trong Bronze layer

**Nguyên nhân:** Debezium encode NUMERIC dạng Base64 (`"amt": "AfE="`)

**Giải pháp:**

```json
{
  "decimal.handling.mode": "double"
}
```

**File:** `connector-config.json`

**Kiểm tra:**

```bash
docker exec kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic postgres.public.transactions \
  --max-messages 1 | grep amt
```

Expected: `"amt": 23.45` (NOT `"AfE="`)

### 5.2. Bug #2: Hive Metastore Restart Issue

**Triệu chứng:** `ERROR: relation "BUCKETING_COLS" already exists`

**Nguyên nhân:** Init script chạy lại khi restart

**Giải pháp:** Custom entrypoint với schema check

```bash
SCHEMA_EXISTS=$(psql -h metastore-db -U hive -d metastore -tAc \
  "SELECT 1 FROM information_schema.tables WHERE table_name='BUCKETING_COLS'" || echo "0")

if [ "$SCHEMA_EXISTS" = "1" ]; then
  echo "✅ Schema exists, skipping init"
else
  /opt/hive/bin/schematool -dbType postgres -initSchema
fi
```

**File:** `deployment/hive-metastore/entrypoint.sh`

### 5.3. Bug #3: Port Confusion (8080 vs 8081)

**Triệu chứng:** Airflow không truy cập được từ browser

**Nguyên nhân:** Spark Master UI và Airflow đều dùng 8080

**Giải pháp:** Đổi Airflow → 8081

```yaml
# docker-compose.yml
airflow-webserver:
  ports:
    - "8081:8080" # Host:Container
```

**Ports mapping:**

- Spark Master UI: 8080 (container only, không expose)
- Airflow UI: 8081 (host) → 8080 (container)

### 5.4. Bug #4: ML Training Low Sample Count

**Triệu chứng:** "Training with only 20 fraud samples"

**Nguyên nhân:** KHÔNG PHẢI LỖI - đây là **normal** với fraud rate 0.5-1%

**Giải thích:**

```
Total: 10,000 transactions
Fraud rate: 0.5%
Fraud samples: 10,000 * 0.005 = 50

After train/test split (80/20):
Training fraud: 50 * 0.8 = 40
Testing fraud: 50 * 0.2 = 10
```

**Số lượng thấp là EXPECTED** với imbalanced dataset. Undersampling sẽ giảm non-fraud xuống bằng fraud (1:1 ratio).

**Không cần fix** - đây không phải bug. Training data sau khi balance sẽ nhỏ hơn test data.

### 5.5. Bug #5: Checkpoint Recovery Failed

**Triệu chứng:** Spark streaming restart → reprocess all data

**Nguyên nhân:** Checkpoint schema mismatch

**Giải pháp:** Xóa checkpoint cũ khi đổi schema

```bash
docker exec minio mc rm -r --force minio/lakehouse/checkpoints/bronze
docker-compose restart spark-streaming
```

**Prevention:** Version checkpoints

```python
checkpoint_path = f"s3a://lakehouse/checkpoints/bronze_v{SCHEMA_VERSION}"
```

### 5.6. Bug #6: FastAPI Model Loading Failed

**Triệu chứng:** `No model found in Production stage`

**Nguyên nhân:** Model chưa được promote to Production

**Giải pháp:**

```bash
# Trigger model training
docker exec airflow-scheduler airflow dags trigger model_retraining_taskflow

# Check MLflow
curl http://localhost:5001/api/2.0/mlflow/registered-models/get?name=fraud_detection_model

# Manual promote (if needed)
# Trong MLflow UI: Models → fraud_detection_model → Transition to Production
```

### 5.7. Bug #7: Slack Alert 404 - no_service

**Triệu chứng:** `❌ Slack alert failed: 404 - no_service`

**Nguyên nhân:** Webhook URL không hợp lệ hoặc đã bị deleted

**Giải pháp:**

1. Tạo webhook mới: https://api.slack.com/apps → Incoming Webhooks
2. Cập nhật `SLACK_WEBHOOK_URL` trong `.env`
3. Rebuild: `docker-compose up -d --build spark-realtime-prediction`

**Test webhook:**

```bash
curl -X POST $SLACK_WEBHOOK_URL \
  -H "Content-Type: application/json" \
  -d '{"text":"Test from Fraud Detection"}'
```

### 5.8. Bug #8: Prediction Time Wrong Timezone

**Triệu chứng:** `prediction_time` là UTC nhưng cần GMT+7

**Giải pháp Option 1:** Đổi PostgreSQL timezone

```bash
docker exec postgres psql -U postgres -c \
  "ALTER DATABASE frauddb SET timezone TO 'Asia/Ho_Chi_Minh';"
```

**Giải pháp Option 2:** Đổi trong code

```python
# Thay NOW() bằng:
prediction_time = CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Ho_Chi_Minh'
```

---

## 6. FAQ

### Q1: Tại sao cần Hive Metastore nếu có Trino Delta catalog?

**A:** Hive Metastore là **optional** metadata cache.

- **Trino Delta catalog**: Query data trực tiếp từ `_delta_log/` (primary method)
- **Hive Metastore**: Cache metadata để tăng tốc `SHOW TABLES` (~100ms vs ~1-2s)

**Không bắt buộc** - có thể xóa service này nếu không cần.

### Q2: Tại sao không dùng Hive catalog để query data?

**A:** Hive không hiểu Delta Lake transaction log.

- Hive chỉ thấy Parquet files, không thấy `_delta_log/`
- Delta metadata (time travel, ACID) bị mất
- **Best practice**: Dùng Delta catalog cho queries

### Q3: Data producer checkpoint hoạt động như nào?

**A:** Producer lưu offset vào `producer_checkpoint` table.

```sql
CREATE TABLE producer_checkpoint (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    last_row_index INTEGER,
    last_trans_num VARCHAR(100),
    updated_at TIMESTAMP
);
```

**Flow:**

1. Producer đọc last_row_index từ checkpoint
2. Resume từ dòng tiếp theo
3. Sau mỗi batch (1000 rows), update checkpoint
4. Nếu crash → restart từ last checkpoint

**Benefits:**

- No duplicates
- Resume safely
- Idempotent

### Q4: Bulk load có an toàn không? Có duplicate data không?

**A:** An toàn. `trans_num` là PRIMARY KEY → tự động reject duplicates.

```sql
-- Bulk load
\COPY transactions(...) FROM 'data.csv' ...

-- Nếu trans_num exist → PostgreSQL throw error
-- Debezium chỉ capture INSERT thành công
```

**No duplicates** guaranteed bởi database constraint.

### Q5: Health check indicators ý nghĩa gì?

**A:** Docker health checks:

```yaml
healthcheck:
  test: ["CMD", "pg_isready", "-U", "postgres"]
  interval: 10s
  timeout: 5s
  retries: 5
```

**States:**

- `starting`: Container đang khởi động
- `healthy`: Service ready
- `unhealthy`: Health check failed (5 retries)

**Check:** `docker-compose ps` → cột STATUS

### Q6: Khi nào cần restart services?

**A:** Restart khi:

✅ **Phải restart:**

- Đổi `.env` variables
- Update code (rebuild required)
- Service crash (unhealthy)
- Config file changes

❌ **Không cần restart:**

- Data changes (INSERT/UPDATE)
- ML model retrain (FastAPI hot reload)
- Trino query errors

**Commands:**

```bash
# Restart specific service
docker-compose restart <service_name>

# Rebuild and restart
docker-compose up -d --build <service_name>
```

### Q7: Backup strategy cho production?

**A:** 3 layers:

**1. PostgreSQL (OLTP):**

```bash
# Daily backup
docker exec postgres pg_dump -U postgres frauddb > backup_$(date +%Y%m%d).sql

# Restore
docker exec -i postgres psql -U postgres frauddb < backup.sql
```

**2. Delta Lake (Lakehouse):**

```bash
# Snapshot MinIO bucket
docker exec minio mc mirror minio/lakehouse /backup/lakehouse_$(date +%Y%m%d)

# Or use Delta table time travel
SELECT * FROM delta.`s3a://lakehouse/gold/fact_transactions` VERSION AS OF 10
```

**3. MLflow Models:**

```bash
# Copy mlruns folder
docker cp mlflow:/mlflow/mlruns ./backup/mlruns_$(date +%Y%m%d)
```

**Recommendation:** Automate với Airflow DAG (daily backup).

### Q8: Alert system đã được implement chưa?

**A:** **PARTIAL** - chỉ có risk_level trong API response.

**Implemented:**

- ✅ FastAPI `/predict` returns `risk_level` (LOW/MEDIUM/HIGH)
- ✅ Chatbot display risk level
- ✅ Slack alerts (real-time service)

**NOT Implemented:**

- ❌ Dashboard alerts
- ❌ Email notifications
- ❌ SMS alerts
- ❌ Webhook integrations (ngoài Slack)

**Future work:** Integrate với notification services.

### Q9: SQL Views trong Gold layer có được execute không?

**A:** **NO** - SQL scripts chỉ là **documentation**.

**Files:**

- `sql/gold_layer_views.sql`
- `sql/gold_layer_views_delta.sql`

**Status:** Code exists nhưng **KHÔNG được execute** tự động.

**Manual execution:**

```bash
docker exec trino trino --catalog delta --schema default \
  --file /sql/gold_layer_views_delta.sql
```

**Lý do:** Views không cần thiết cho current use cases (Chatbot query fact tables trực tiếp).

### Q10: Làm sao tăng performance cho Spark jobs?

**A:** 5 optimizations:

**1. Partition pruning:**

```python
df.write.partitionBy("year", "month", "day").format("delta").save(path)
```

**2. Z-ordering:**

```sql
OPTIMIZE delta.`s3a://lakehouse/gold/fact_transactions`
ZORDER BY (trans_num, customer_id)
```

**3. File compaction:**

```sql
OPTIMIZE delta.`s3a://lakehouse/gold/fact_transactions`
```

**4. Vacuum old files:**

```sql
VACUUM delta.`s3a://lakehouse/gold/fact_transactions` RETAIN 168 HOURS
```

**5. Tune shuffle partitions:**

```python
spark.conf.set("spark.sql.shuffle.partitions", 200)  # Default
# Giảm xuống 50-100 cho small data
```

### Q11: Schema evolution trong Delta Lake hoạt động như nào?

**A:** Delta Lake support 2 modes:

**1. Add columns (automatic):**

```python
df_with_new_col.write.format("delta").mode("append").save(path)
# New column tự động thêm vào schema
```

**2. Change column type (manual):**

```sql
ALTER TABLE delta.`s3a://lakehouse/gold/fact_transactions`
ALTER COLUMN amt TYPE DECIMAL(10,2)
```

**3. Merge schema:**

```python
df.write.format("delta") \
  .option("mergeSchema", "true") \
  .mode("append") \
  .save(path)
```

**Lưu ý:** Schema changes backward compatible (old readers still work).

### Q12: Tại sao không dùng Hive catalog cho Trino queries?

**A:** Hive Metastore không hiểu Delta transaction log.

**Hive sees:**

- `data.parquet` files
- Directory structure

**Hive DOESN'T see:**

- `_delta_log/` (transaction history)
- ACID transactions
- Time travel
- Deleted files

**Consequence:** Hive queries có thể return wrong results (stale data, deleted rows).

**Solution:** Dùng Delta catalog (reads `_delta_log/` correctly).

### Q13: Data producer checkpoint có thread-safe không?

**A:** **YES** - với `ON CONFLICT` upsert.

```sql
INSERT INTO producer_checkpoint (id, last_row_index, ...)
VALUES (1, ?, ...)
ON CONFLICT (id) DO UPDATE SET
    last_row_index = EXCLUDED.last_row_index,
    updated_at = NOW();
```

**Single row với id=1** → atomic updates → thread-safe.

**Nếu chạy multiple producers:** Cần distributed coordination (Kafka consumer groups thay vì manual checkpoint).

### Q14: Bulk load có trigger CDC events không?

**A:** **YES** - mọi INSERT đều trigger CDC.

```bash
# Bulk load 50K rows
\COPY transactions(...) FROM 'data.csv' ...

# Debezium capture 50K CDC events → Kafka
# Spark streaming process 50K events → Bronze
```

**Lưu ý:** Bulk load lớn (1M+ rows) có thể làm chậm Kafka. Khuyến nghị:

- Bulk load offline hours
- Hoặc tăng Kafka retention
- Hoặc pause streaming jobs

---

## 7. Common Operations

### 7.1. Reset Everything

```bash
# Stop all services
docker-compose down

# Remove volumes (DELETE ALL DATA)
docker volume prune -f

# Remove images
docker image prune -a -f

# Rebuild from scratch
docker-compose up -d --build

# Re-initialize
# 1. Load data
# 2. Train model
# 3. Verify
```

### 7.2. View Logs

```bash
# Real-time logs
docker logs <service_name> -f --tail 100

# Last N lines
docker logs <service_name> --tail 50

# Time range
docker logs <service_name> --since 10m

# Save to file
docker logs <service_name> > logs.txt 2>&1
```

### 7.3. Clean Disk Space

```bash
# Remove stopped containers
docker container prune -f

# Remove unused images
docker image prune -a -f

# Remove unused volumes
docker volume prune -f

# Remove unused networks
docker network prune -f

# All-in-one
docker system prune -a --volumes -f

# Check disk usage
docker system df
```

### 7.4. Migration History (Reference)

**Lịch sử migrations (deprecated - giờ dùng auto-init):**

1. **v1:** Manual schema creation (`CREATE TABLE` statements)
2. **v2:** Add `fraud_predictions` table
3. **v3:** Add `chat_history` table with `sql_query` column
4. **v4:** Add UNIQUE constraint on `fraud_predictions.trans_num`
5. **v5:** Add foreign key `fraud_predictions → transactions`
6. **Current:** All merged into `database/init_postgres.sql` (idempotent)

**Hiện tại:** Không cần manual migrations. PostgreSQL auto-init on first start.

---

## 8. Testing

### 8.1. Unit Tests

**Structure:**

```
tests/
├── unit/
│   ├── test_feature_engineering.py
│   ├── test_schema_loader.py
│   └── test_api_endpoints.py
├── integration/
│   ├── test_spark_jobs.py
│   └── test_end_to_end_flow.py
└── fixtures/
    └── sample_data.csv
```

**Example:**

```python
# tests/unit/test_feature_engineering.py
import pytest
from app.feature_engineering import calculate_distance

def test_calculate_distance():
    # NYC to LA (~3944 km)
    dist = calculate_distance(40.7128, -74.0060, 34.0522, -118.2437)
    assert 3900 < dist < 4000

def test_categorize_amount():
    from app.feature_engineering import categorize_amount
    assert categorize_amount(5) == 0      # < $10
    assert categorize_amount(25) == 1     # $10-$50
    assert categorize_amount(75) == 2     # $50-$100
    assert categorize_amount(5000) == 6   # > $1000
```

**Run tests:**

```bash
cd services/fraud-detection-api
pytest tests/ -v
```

### 8.2. Integration Tests

```python
# tests/integration/test_end_to_end_flow.py
def test_full_fraud_detection_flow():
    # 1. Insert transaction to PostgreSQL
    conn = psycopg2.connect(...)
    cur = conn.cursor()
    cur.execute("INSERT INTO transactions (...) VALUES (...) RETURNING trans_num")
    trans_num = cur.fetchone()[0]

    # 2. Wait for CDC
    time.sleep(5)

    # 3. Check Bronze layer
    spark = SparkSession.builder.getOrCreate()
    bronze_df = spark.read.format("delta").load("s3a://lakehouse/bronze/transactions")
    assert bronze_df.filter(f"trans_num = '{trans_num}'").count() == 1

    # 4. Trigger prediction
    response = requests.post("http://localhost:8000/predict/raw", json={...})
    assert response.status_code == 200

    # 5. Check fraud_predictions table
    cur.execute(f"SELECT * FROM fraud_predictions WHERE trans_num = '{trans_num}'")
    prediction = cur.fetchone()
    assert prediction is not None
```

### 8.3. Performance Tests

```python
# tests/performance/test_api_latency.py
import time

def test_prediction_latency():
    start = time.time()
    response = requests.post("http://localhost:8000/predict/raw", json={
        "amt": 500.0,
        "hour": 14,
        "distance_km": 50.0
    })
    end = time.time()

    latency_ms = (end - start) * 1000
    assert latency_ms < 100  # < 100ms
    assert response.status_code == 200
```

---

## CI/CD & Future Work

### Limitations

**Current:**

- Manual deployment (Docker Compose)
- No automated testing
- No continuous deployment
- No monitoring/alerting system

**Planned improvements:**

- GitHub Actions for CI/CD
- Automated testing pipeline
- Kubernetes deployment
- Prometheus + Grafana monitoring
- Automated backup & recovery

---

**Tài liệu liên quan:**

- [Setup Guide](SETUP.md) - Cài đặt hệ thống
- [User Manual](USER_MANUAL.md) - Hướng dẫn sử dụng
- [Architecture](ARCHITECTURE.md) - Kiến trúc chi tiết
- [Changelog](CHANGELOG.md) - Lịch sử thay đổi đầy đủ
