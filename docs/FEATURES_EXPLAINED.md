
# Feature Engineering - Fraud Detection

## 📊 Raw Dataset (Sparkov)

**20 raw fields:**

| Category    | Fields                                                                     | Count |
| ----------- | -------------------------------------------------------------------------- | ----- |
| Transaction | `amt`, `merchant`, `category`, `trans_date_trans_time`, `cc_num` | 5     |
| Customer    | `first`, `last`, `gender`, `street`, `city`, `state`, `zip`  | 7     |
| Location    | `lat`, `long`, `city_pop`, `merch_lat`, `merch_long`             | 5     |
| Metadata    | `job`, `dob`, `trans_num`, `unix_time`                             | 4     |
| Label       | `is_fraud`                                                               | 1     |

---

## 🛠️ Feature Engineering (Silver Layer)

### **15 Numerical Features (Used by Model)**

```python
# 1. Amount Features (5)
amt                    # Raw transaction amount
log_amount            # log(1 + amt) - handles skewness
is_zero_amount        # Binary: amt == 0
is_high_amount        # Binary: amt > $500
amount_bin            # Categorical: 0-50, 50-150, 150-300, 300-500, >500

# 2. Distance Features (2)
distance_km           # Haversine(customer_location, merchant_location)
is_distant_transaction # Binary: distance > 50km

# 3. Demographics (2)
age                   # Current_year - birth_year
gender_encoded        # M=1, F=0

# 4. Time Features (6)
hour                  # 0-23
day_of_week          # 0=Mon, 6=Sun
is_weekend           # Binary: Sat/Sun
is_late_night        # Binary: 0-6AM or 11PM-12AM
hour_sin             # Cyclical encoding
hour_cos             # Cyclical encoding
```

### **2 Categorical Features (Not Used Yet)**

```python
merchant             # String (needs encoding)
category             # String (e.g., grocery_pos, gas_transport)
```

**Note:** Model hiện tại chưa dùng merchant/category vì chưa implement encoding (One-Hot hoặc Target Encoding).

---

## 🤖 Chatbot Input Mapping

### **User nhập (6-7 fields):**

```
amt=850              # Required
hour=2               # Optional (default=12)
distance_km=150      # Optional (default=10)
age=35               # Optional (default=35)
merchant="Shop A"    # Optional (not used by model)
category="shopping"  # Optional (not used by model)
day_of_week=0        # Optional (default=0)
```

### **API tự tính (8 fields):**

```python
log_amount = log(1 + 850) = 6.75
is_high_amount = 1  # amt > 500
is_zero_amount = 0
amount_bin = 4      # 500-1000 range
is_distant = 1      # distance > 50km
gender_encoded = 0  # Default Female (not collected)
is_weekend = 0      # day_of_week=0 (Monday)
is_late_night = 1   # hour=2 (2AM)
hour_sin = sin(2π*2/24) = 0.5
hour_cos = cos(2π*2/24) = 0.866
```

### **Total features sent to model: 15**

---

## ✅ Validation

### **Tại sao chatbot input ít?**

**Lý do kỹ thuật:**

1. **Separation of Concerns**: User không cần biết feature engineering
2. **API-driven**: Logic tính toán tập trung ở API (dễ maintain)
3. **User Experience**: Form đơn giản hơn (7 fields thay vì 15)

**Trade-off:**

| Aspect      | Pro                                             | Con                                          |
| ----------- | ----------------------------------------------- | -------------------------------------------- |
| Accuracy    | ✅ Model dùng đủ 15 features                 | ❌ Thiếu gender, exact location             |
| UX          | ✅ Form ngắn gọn                              | ⚠️ Phải nhập distance thủ công         |
| Flexibility | ✅ Thay đổi model không ảnh hưởng chatbot | ⚠️ Chatbot không control được defaults |

---

## 📝 Code Flow

### Manual Prediction Form

```python
# 1. User fills form (7 inputs)
amt = 100.0
hour = 14
distance_km = 10.0
age = 35
day_of_week = 0
merchant = "Shop A"
category = "shopping_net"

# 2. _build_features() generates 20 fields
features = {
    # Original 7
    "amt": amt,
    "hour": hour,
    "distance_km": distance_km,
    "age": age,
    "day_of_week": day_of_week,
    "merchant": merchant,
    "category": category,

    # Auto-generated 8
    "log_amount": 4.61,
    "is_high_amount": 0,
    "is_zero_amount": 0,
    "amount_bin": 2,
    "is_distant_transaction": 0,
    "is_weekend": 0,
    "is_late_night": 0,
    "hour_sin": -0.5,
    "hour_cos": 0.866,

    # Defaults 5
    "gender_encoded": 0,
    "trans_num": "MANUAL_20250110120000"
}

# 3. Send to API
POST /predict/raw
{
    "amt": 100.0,
    "hour": 14,
    "distance_km": 10.0,
    "age": 35,
    "merchant": "Shop A",
    "category": "shopping_net"
}

# 4. API responds
{
    "is_fraud_predicted": 0,
    "fraud_probability": 0.15,
    "risk_level": "LOW",
    ...
}
```

### Batch CSV Upload

```python
# 1. User uploads CSV with 7 columns
df = pd.read_csv("batch.csv")
# amt,hour,distance_km,age,day_of_week,merchant,category

# 2. For each row, call _build_features()
for _, row in df.iterrows():
    features = ManualPredictionForm()._build_features(
        amt=row['amt'],
        hour=row['hour'],
        # ...
    )
    # Each features dict has 20 fields
    transactions.append(features)

# 3. Call batch API
result = predict_batch_api(transactions)
```

---

## 🔧 Troubleshooting

### Error: "X has 20 features, but model expects 15"

**Nguyên nhân:** Code cũ truyền 20 features (15 + 5 placeholders)
**Fix:** Đã fix - chỉ truyền 15 features đúng thứ tự

### Error: "422 Unprocessable Entity" ở batch predict

**Nguyên nhân:** API expect `list[TransactionFeatures]` với đầy đủ 20 fields
**Fix:** `_build_features()` đã generate đủ 20 fields

### Manual prediction bị duplicate info

**Nguyên nhân:** Hiển thị explanation 2 lần (summary + expander)
**Fix:** Đã fix - summary ngắn gọn, details trong expander

---

## 📚 Related Files

- **Feature Building:** `services/fraud-chatbot/src/components/forms.py` → `_build_features()`
- **Model Training:** `spark/app/ml_training_sklearn.py` → `prepare_features()`
- **API Prediction:** `services/fraud-detection-api/app/main.py` → `/predict`, `/predict/explained`
- **Feature Order:** Must match training exactly (15 features)

---

**Last Updated:** 2025-12-10
**Author:** GitHub Copilot (Claude Sonnet 4.5)
