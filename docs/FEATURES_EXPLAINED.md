# Feature Engineering - Fraud Detection

## 📊 Tổng quan

Model ML sử dụng **15 features** để dự đoán gian lận, nhưng user chỉ cần nhập **7 thông tin cơ bản**. Hệ thống tự động tính toán 8 features còn lại.

---

## ✍️ User Input (7 fields)

Những gì user cần nhập trong Manual Prediction hoặc CSV:

| Field         | Type   | Mô tả                          | Ví dụ          |
| ------------- | ------ | ------------------------------ | -------------- |
| `amt`         | float  | Số tiền giao dịch              | 100.0          |
| `hour`        | int    | Giờ giao dịch (0-23)           | 14             |
| `distance_km` | float  | Khoảng cách từ nhà             | 10.0           |
| `age`         | int    | Tuổi khách hàng                | 35             |
| `day_of_week` | int    | Ngày trong tuần (0=Mon, 6=Sun) | 0              |
| `merchant`    | string | Tên merchant (optional)        | "Shop A"       |
| `category`    | string | Loại giao dịch (optional)      | "shopping_net" |

---

## 🤖 Auto-Generated Features (8 fields)

Hệ thống tự động tính toán từ 7 input trên:

### 1. Amount Features (4)

```python
log_amount = math.log1p(amt)  # Log transformation
is_high_amount = 1 if amt > 500 else 0
is_zero_amount = 1 if amt == 0 else 0

# Amount bin (0-5)
if amt == 0: amount_bin = 0
elif amt <= 50: amount_bin = 1
elif amt <= 150: amount_bin = 2
elif amt <= 300: amount_bin = 3
elif amt <= 500: amount_bin = 4
else: amount_bin = 5
```

### 2. Distance Feature (1)

```python
is_distant_transaction = 1 if distance_km > 50 else 0
```

### 3. Time Features (3)

```python
is_weekend = 1 if day_of_week in [5, 6] else 0
is_late_night = 1 if hour < 6 or hour >= 23 else 0
hour_sin = math.sin(2 * math.pi * hour / 24)  # Cyclic encoding
hour_cos = math.cos(2 * math.pi * hour / 24)
```

---

## 🎯 Final 15 Features for Model

Thứ tự features **PHẢI ĐÚNG** với training model:

```python
[
    amt,                      # 1. Original amount
    log_amount,              # 2. Log transformed
    is_zero_amount,          # 3. Zero amount flag
    is_high_amount,          # 4. High amount flag (>500)
    amount_bin,              # 5. Amount category (0-5)
    distance_km,             # 6. Distance from home
    is_distant_transaction,  # 7. Far transaction flag (>50km)
    age,                     # 8. Customer age
    gender_encoded,          # 9. Gender (0=F, 1=M) - DEFAULT 0
    hour,                    # 10. Hour of day
    day_of_week,             # 11. Day of week
    is_weekend,              # 12. Weekend flag
    is_late_night,           # 13. Late night flag
    hour_sin,                # 14. Hour sine
    hour_cos                 # 15. Hour cosine
]
```

**Note:** `gender_encoded` mặc định là 0 (Female) vì không có trong input form.

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
    "hour_cos": -0.866,

    # Defaults
    "gender_encoded": 0,
    "trans_num": "MANUAL_20251209..."
}

# 3. API extracts 15 features in correct order
feature_values = [
    features.amt,
    features.log_amount,
    features.is_zero_amount,
    # ... (15 features total)
]

# 4. Model predicts
X = np.array(feature_values).reshape(1, -1)  # Shape: (1, 15)
prediction = model.predict(X)
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

## ❓ FAQs

### Q: Tại sao model cần 15 features nhưng user chỉ nhập 7?

**A:** Để đơn giản hóa UX. User không cần biết về feature engineering (log transformation, cyclic encoding...). Hệ thống tự động tính toán.

### Q: Điền giá trị mặc định như thế nào?

**A:**

- `gender_encoded = 0` (Female)
- Các features khác được tính từ user input
- Không có giá trị "random" - tất cả deterministic

### Q: Batch CSV có thể thiếu columns không?

**A:** Có, optional columns (merchant, category) có thể bỏ trống. Code sẽ dùng `row.get('merchant')` → None.

### Q: `/predict/explained` endpoint khác gì `/predict`?

**A:**

- `/predict`: Trả kết quả ngắn gọn
- `/predict/explained`: Trả kết quả + explanation text (Vietnamese) + model_info
- Chatbot dùng `/predict/explained` để có thêm context cho user

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
