# Chatbot Refactoring - Architecture Improvements

## 📋 Tóm tắt

Chatbot đã được refactor để tách biệt logic nghiệp vụ khỏi code, cho phép:

- **Business Analyst** có thể sửa prompts và business rules mà không cần biết code
- **Data Engineer** có thể thay đổi schema database mà chatbot tự động cập nhật
- **ML Engineer** có thể thay model/features mà không cần sửa chatbot

---

## 🎯 3 Cải tiến chính

### 1. **Kiến trúc: Logic tính toán chuyển về API**

**Trước đây:**

```python
# Chatbot phải tự tính toán features
features = {
    "amt": amt,
    "log_amount": math.log1p(amt),  # ← Chatbot tự tính log
    "hour_sin": math.sin(2 * math.pi * hour / 24),  # ← Chatbot tự tính sin/cos
    "hour_cos": math.cos(2 * math.pi * hour / 24),
    ...
}
api.predict(features)  # Gửi features đã tính sẵn
```

**Bây giờ:**

```python
# Chatbot chỉ gửi raw data
api.predict_raw(amt=850, hour=2)  # ← API tự tính log, sin/cos bên trong
```

**Lợi ích:**

- ✅ Thay đổi model (thêm/bớt features) → Chỉ sửa API, chatbot không cần động
- ✅ Thay công thức tính toán → Chỉ sửa 1 nơi (API), không sửa chatbot
- ✅ Chatbot đơn giản hơn, dễ maintain

**Files thay đổi:**

- `services/fraud-detection-api/app/feature_engineering.py` (NEW) - Tập trung logic tính toán
- `services/fraud-detection-api/app/main.py` - Thêm endpoint `/predict/raw`
- `services/fraud-chatbot/src/core/tools.py` - Bỏ tính toán, chỉ gửi raw data
- `services/fraud-chatbot/src/utils/api_client.py` - Thêm `predict_fraud_raw()`

---

### 2. **Database: Tự động hóa Schema (Dynamic Schema)**

**Trước đây:**

```python
# agent.py - Hardcoded schema
prompt = """
...
Bảng có sẵn:
- state_summary: state, fraud_rate, total_transactions  # ← Copy-paste thủ công
- merchant_analysis: merchant, fraud_count...  # ← Thêm bảng mới phải sửa code
...
"""
```

**Bây giờ:**

```python
# agent.py - Dynamic schema
schema_loader = get_schema_loader()
schema_text = schema_loader.format_schema_for_prompt()  # ← Auto query Trino
prompt = prompt_template.format(database_schema=schema_text)  # ← Inject vào prompt
```

**Lợi ích:**

- ✅ Thêm bảng mới trong Trino → Chatbot tự động biết
- ✅ Sửa tên cột → Chatbot tự động cập nhật
- ✅ Không cần maintain 2 nơi (database + chatbot code)

**Files thay đổi:**

- `services/fraud-chatbot/src/utils/schema_loader.py` (NEW) - Query Trino để lấy schema
- `services/fraud-chatbot/src/core/agent.py` - Load schema động, inject vào prompt

---

### 3. **Quản lý Cấu hình: Tách rời Code và Lời dẫn**

**Trước đây:**

```python
# agent.py - Hardcoded prompt
prompt = """
Bạn là chuyên gia phân tích gian lận tài chính...
- Nếu xác suất > 0.7 thì HIGH RISK  # ← Business rule trong code
- Nếu xác suất > 0.3 thì MEDIUM RISK
...
"""
```

**Bây giờ:**

```yaml
# config/prompts.yaml - Business Analyst có thể sửa
system_prompt: |
  Bạn là chuyên gia phân tích gian lận tài chính...
  {database_schema}  # ← Dynamic injection

# config/business_rules.yaml - Business rules tách riêng
risk_thresholds:
  high_risk: 0.7
  medium_risk: 0.3

response_format:
  risk_emojis:
    HIGH: "🚨"
    MEDIUM: "⚠️"
```

**Lợi ích:**

- ✅ Business Analyst sửa YAML → Thay đổi giọng điệu, ngưỡng rủi ro
- ✅ Không cần biết Python
- ✅ Version control riêng cho business logic

**Files thay đổi:**

- `services/fraud-chatbot/config/prompts.yaml` (NEW) - System prompts
- `services/fraud-chatbot/config/business_rules.yaml` (NEW) - Risk thresholds, emojis, messages
- `services/fraud-chatbot/src/utils/config_loader.py` (NEW) - Load YAML configs
- `services/fraud-chatbot/src/core/agent.py` - Load prompt từ config thay vì hardcode

---

## 🏗️ Cấu trúc file mới

```
services/fraud-chatbot/
├── config/  (NEW)
│   ├── prompts.yaml             # System prompts, tool descriptions
│   └── business_rules.yaml      # Risk thresholds, emojis, recommendations
├── src/
│   ├── core/
│   │   ├── agent.py             # REFACTORED: Load config + dynamic schema
│   │   └── tools.py             # REFACTORED: Gửi raw data thay vì features
│   ├── utils/
│   │   ├── api_client.py        # REFACTORED: Thêm predict_fraud_raw()
│   │   ├── config_loader.py     # NEW: Load YAML configs
│   │   └── schema_loader.py     # NEW: Query Trino schema
│   ...

services/fraud-detection-api/
├── app/
│   ├── main.py                  # REFACTORED: Thêm /predict/raw endpoint
│   └── feature_engineering.py   # NEW: Tập trung logic tính features
```

---

## 📊 So sánh trước & sau

| Aspect                  | Trước                         | Sau                                     |
| ----------------------- | ----------------------------- | --------------------------------------- |
| **Feature Engineering** | Chatbot tự tính log, sin/cos  | API tự tính, chatbot gửi raw data       |
| **Database Schema**     | Hardcode trong prompt         | Dynamic load từ Trino                   |
| **Business Rules**      | Hardcode trong Python         | Config YAML, BA tự sửa                  |
| **Prompt Management**   | String trong code             | File YAML riêng                         |
| **Maintainability**     | Sửa nhiều nơi khi có thay đổi | Sửa 1 nơi (config hoặc API)             |
| **Testability**         | Khó test riêng từng phần      | Dễ test (config, schema, API tách biệt) |

---

## 🔄 Migration Path

### Bước 1: Update API (Backend)

```bash
cd services/fraud-detection-api
# Đã có feature_engineering.py và /predict/raw endpoint
docker compose up -d --build fraud-detection-api
```

### Bước 2: Update Chatbot

```bash
cd services/fraud-chatbot
# Đã có config/, schema_loader.py, config_loader.py
pip install pyyaml  # Thêm dependency
docker compose up -d --build fraud-chatbot
```

### Bước 3: Verify

```python
# Test API trực tiếp
curl -X POST http://localhost:8000/predict/raw \
  -H "Content-Type: application/json" \
  -d '{"amt": 850, "hour": 2, "distance_km": 100}'

# Test chatbot
# http://localhost:8501
# "Dự đoán giao dịch $850 lúc 2h sáng xa 100km"
```

---

## 📝 Cách sử dụng cho Business Analyst

### Thay đổi ngưỡng rủi ro

**File:** `config/business_rules.yaml`

```yaml
risk_thresholds:
  high_risk: 0.8 # Thay từ 0.7 → 0.8 (strict hơn)
  medium_risk: 0.4 # Thay từ 0.3 → 0.4
```

### Thay đổi message

```yaml
response_format:
  risk_messages:
    HIGH: "⛔ NGUY HIỂM: Giao dịch có dấu hiệu gian lận rất cao!"
    MEDIUM: "⚡ CHÚ Ý: Giao dịch cần xem xét thêm."
```

### Thay đổi prompt

**File:** `config/prompts.yaml`

```yaml
system_prompt: |
  Bạn là trợ lý AI chuyên về an ninh tài chính, hỗ trợ ngân hàng phát hiện gian lận...
  # Sửa giọng điệu, thêm/bớt hướng dẫn
```

**Không cần restart container**, config sẽ load lại khi agent khởi tạo mới (có cache, nên clear cache nếu test).

---

## 🧪 Testing

### Test Feature Engineering (API)

```python
# services/fraud-detection-api/app/feature_engineering.py
python feature_engineering.py  # Run test cases
```

### Test Schema Loader (Chatbot)

```python
# services/fraud-chatbot/src/utils/schema_loader.py
python schema_loader.py  # Query Trino và print schema
```

### Test Config Loader (Chatbot)

```python
# services/fraud-chatbot/src/utils/config_loader.py
python config_loader.py  # Load YAML và print configs
```

### End-to-end Test

```bash
# 1. Chatbot gửi raw data
curl http://localhost:8501
# Query: "Check giao dịch $1500 lúc 3h sáng"

# 2. Verify API log
docker logs fraud-detection-api --tail 20
# Should see: "🔧 Engineered features..." with calculated log_amount, hour_sin, etc.
```

---

## 🚀 Benefits Summary

### For Developers

- ✅ **Separation of Concerns**: Logic tính toán ở API, prompt ở config, schema ở database
- ✅ **Easier Testing**: Test API, chatbot, config independently
- ✅ **Maintainability**: Thay đổi 1 nơi thay vì nhiều nơi

### For Business Analysts

- ✅ **No Code Required**: Sửa YAML để thay prompt, rules, messages
- ✅ **Version Control**: Theo dõi thay đổi business logic qua Git
- ✅ **Faster Iteration**: Không cần chờ developer deploy code

### For Data Scientists

- ✅ **Feature Engineering Flexibility**: Thay đổi features trong API, chatbot không ảnh hưởng
- ✅ **Model Swapping**: Thay model/version, chatbot tự động dùng luôn
- ✅ **A/B Testing**: Dễ dàng test nhiều model versions

---

## 📚 Related Documentation

- [API Feature Engineering](../../fraud-detection-api/app/feature_engineering.py) - Logic tính features
- [Config Prompts](../config/prompts.yaml) - System prompts
- [Config Business Rules](../config/business_rules.yaml) - Risk thresholds
- [Schema Loader](../src/utils/schema_loader.py) - Dynamic schema from Trino
- [Config Loader](../src/utils/config_loader.py) - YAML config management

---

**Status:** ✅ Implemented (2025-12-10)  
**Version:** 2.0.0  
**Breaking Changes:** API có endpoint mới `/predict/raw`, chatbot code thay đổi đáng kể
