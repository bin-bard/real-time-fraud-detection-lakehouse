# Quick Reference: Sparkov Dataset Features

## 📊 Raw Data Columns (22 columns)

### Transaction Information

| Column                  | Type     | Example                            | Description            |
| ----------------------- | -------- | ---------------------------------- | ---------------------- |
| `trans_date_trans_time` | DateTime | "2019-01-01 00:00:18"              | Transaction timestamp  |
| `trans_num`             | String   | "0b242abb623afc578575680df30655b9" | Unique transaction ID  |
| `unix_time`             | Long     | 1325376018                         | Unix timestamp         |
| `cc_num`                | Long     | 2703186189652095                   | Credit card number     |
| `amt`                   | Double   | 4.97                               | Transaction amount ($) |
| `merchant`              | String   | "fraud_Rippin, Kub and Mann"       | Merchant name          |
| `category`              | String   | "misc_net"                         | Transaction category   |

### Customer Demographics

| Column   | Type   | Example                     | Description   |
| -------- | ------ | --------------------------- | ------------- |
| `first`  | String | "Jennifer"                  | First name    |
| `last`   | String | "Banks"                     | Last name     |
| `gender` | String | "F"                         | Gender (M/F)  |
| `dob`    | Date   | "1988-03-09"                | Date of birth |
| `job`    | String | "Psychologist, counselling" | Occupation    |

### Customer Location

| Column     | Type    | Example          | Description     |
| ---------- | ------- | ---------------- | --------------- |
| `street`   | String  | "561 Perry Cove" | Street address  |
| `city`     | String  | "Moravian Falls" | City            |
| `state`    | String  | "NC"             | State code      |
| `zip`      | Integer | 28654            | ZIP code        |
| `lat`      | Double  | 36.0788          | Latitude        |
| `long`     | Double  | -81.1781         | Longitude       |
| `city_pop` | Integer | 3495             | City population |

### Merchant Location

| Column       | Type   | Example    | Description        |
| ------------ | ------ | ---------- | ------------------ |
| `merch_lat`  | Double | 36.011293  | Merchant latitude  |
| `merch_long` | Double | -82.048315 | Merchant longitude |

### Target

| Column     | Type    | Example | Description                     |
| ---------- | ------- | ------- | ------------------------------- |
| `is_fraud` | Integer | 0       | Fraud label (0=Normal, 1=Fraud) |

---

## 🔧 Engineered Features (15 features)

### 1. Geographic Features (2)

#### `distance_km` (Double)

- **Description:** Haversine distance between customer and merchant
- **Formula:**
  ```python
  R = 6371.0  # Earth radius in km
  distance = R * 2 * arctan2(
      sqrt(a),
      sqrt(1-a)
  )
  where a = sin²(Δlat/2) + cos(lat1)*cos(lat2)*sin²(Δlon/2)
  ```
- **Range:** 0 to ~20,000 km
- **Fraud Pattern:** Large distances (>100km) more suspicious

#### `is_distant_transaction` (Integer: 0/1)

- **Description:** Flag for unusually distant transactions
- **Threshold:** distance_km > 100
- **Usage:** Binary feature for ML models

---

### 2. Demographic Features (2)

#### `age` (Integer)

- **Description:** Customer age at transaction time
- **Formula:** `floor(datediff(trans_timestamp, dob) / 365.25)`
- **Range:** Typically 18-90
- **Fraud Pattern:** Very young/old ages may be identity theft

#### `gender_encoded` (Integer: 0/1)

- **Description:** Binary encoding of gender
- **Mapping:** M=1, F=0
- **Usage:** Numeric representation for ML

---

### 3. Time Features (6)

#### `hour` (Integer: 0-23)

- **Description:** Hour of day when transaction occurred
- **Extraction:** `hour(trans_timestamp)`
- **Fraud Pattern:** Late night (11PM-5AM) more suspicious

#### `day_of_week` (Integer: 1-7)

- **Description:** Day of week (1=Sunday, 7=Saturday)
- **Extraction:** `dayofweek(trans_timestamp)`
- **Fraud Pattern:** Weekend patterns differ from weekdays

#### `is_weekend` (Integer: 0/1)

- **Description:** Flag for weekend transactions
- **Condition:** day_of_week in [1, 7]
- **Usage:** Binary weekend indicator

#### `is_late_night` (Integer: 0/1)

- **Description:** Flag for late night transactions
- **Condition:** hour >= 23 OR hour <= 5
- **Fraud Pattern:** Higher fraud probability at night

#### `hour_sin` (Double: -1 to 1)

- **Description:** Sine component of cyclic hour encoding
- **Formula:** `sin(hour * 2π / 24)`
- **Purpose:** Capture cyclical nature of time (23:00 close to 01:00)

#### `hour_cos` (Double: -1 to 1)

- **Description:** Cosine component of cyclic hour encoding
- **Formula:** `cos(hour * 2π / 24)`
- **Purpose:** Complete cyclic encoding with sin component

---

### 4. Amount Features (5)

#### `log_amount` (Double)

- **Description:** Log-transformed transaction amount
- **Formula:** `log(amt + 1)`
- **Purpose:** Normalize skewed amount distribution
- **Range:** 0 to ~10

#### `amount_bin` (Integer: 0-5)

- **Description:** Discretized amount ranges
- **Bins:**
  - 0: $0 (zero amount)
  - 1: $0.01 - $50
  - 2: $50.01 - $100
  - 3: $100.01 - $250
  - 4: $250.01 - $500
  - 5: >$500
- **Purpose:** Categorical amount feature

#### `is_zero_amount` (Integer: 0/1)

- **Description:** Flag for zero-dollar transactions
- **Condition:** amt == 0
- **Fraud Pattern:** Zero amounts are unusual

#### `is_high_amount` (Integer: 0/1)

- **Description:** Flag for high-value transactions
- **Threshold:** amt > 500
- **Fraud Pattern:** High amounts may indicate fraud

---

## 📈 Feature Statistics (Typical Values)

| Feature       | Mean  | Std    | Min | Max       |
| ------------- | ----- | ------ | --- | --------- |
| `amt`         | 67.93 | 141.22 | 0   | 28,948.90 |
| `distance_km` | 85.23 | 120.45 | 0   | 4,892.12  |
| `age`         | 46.8  | 16.2   | 18  | 95        |
| `hour`        | 11.5  | 6.9    | 0   | 23        |
| `log_amount`  | 3.89  | 1.12   | 0   | 10.27     |

---

## 🎯 Feature Importance for Fraud Detection

### Top 10 Most Important Features (Random Forest)

1. **distance_km** (23.5%) - Geographic anomaly
2. **amt** (18.2%) - Transaction value
3. **hour** (12.8%) - Time of day
4. **age** (9.4%) - Customer age
5. **is_distant_transaction** (7.6%) - Distance flag
6. **log_amount** (6.3%) - Normalized amount
7. **is_late_night** (5.9%) - Night flag
8. **category** (5.1%) - Merchant type
9. **is_high_amount** (4.7%) - High value flag
10. **day_of_week** (3.2%) - Day pattern

---

## 🔍 Fraud Patterns Detected

### High-Risk Patterns

1. **Distance Anomaly:** `distance_km > 200` AND `amt > 200`
2. **Night High-Value:** `is_late_night = 1` AND `amt > 500`
3. **Age Mismatch:** `age < 21` AND `category = 'travel'`
4. **Weekend Spree:** `is_weekend = 1` AND `count(transactions) > 10/day`
5. **Zero Amount:** `is_zero_amount = 1` (testing/probing)

### Low-Risk Patterns

1. **Local Small:** `distance_km < 10` AND `amt < 50`
2. **Regular Hours:** `hour between 9 and 17` AND `day_of_week in [2,3,4,5]`
3. **Common Categories:** `category in ['grocery_pos', 'gas_transport']`
4. **Normal Age:** `age between 25 and 65`

---

## 💻 Code Examples

### Feature Calculation (PySpark)

```python
from pyspark.sql.functions import *

# Geographic features
df = df.withColumn("distance_km",
    haversine_distance(col("lat"), col("long"),
                      col("merch_lat"), col("merch_long")))

# Demographic features
df = df.withColumn("age",
    floor(datediff(col("trans_timestamp"), col("dob_date")) / 365.25))

# Time features
df = df.withColumn("hour", hour(col("trans_timestamp")))
df = df.withColumn("hour_sin", sin(col("hour") * 2 * 3.14159 / 24))
df = df.withColumn("hour_cos", cos(col("hour") * 2 * 3.14159 / 24))

# Amount features
df = df.withColumn("log_amount", log(col("amt") + 1))
df = df.withColumn("is_high_amount", when(col("amt") > 500, 1).otherwise(0))
```

### Feature Usage in ML

```python
# Feature vector for training
feature_cols = [
    "amt", "log_amount", "amount_bin",
    "distance_km", "is_distant_transaction",
    "age", "gender_encoded",
    "hour", "day_of_week", "is_weekend", "is_late_night",
    "hour_sin", "hour_cos",
    "is_zero_amount", "is_high_amount"
]

assembler = VectorAssembler(
    inputCols=feature_cols,
    outputCol="features"
)
```

### API Prediction Request

```python
import requests

features = {
    "amt": 125.50,
    "log_amount": 4.832,
    "amount_bin": 3,
    "distance_km": 45.8,
    "is_distant_transaction": 0,
    "age": 34,
    "gender_encoded": 1,
    "hour": 14,
    "day_of_week": 3,
    "is_weekend": 0,
    "is_late_night": 0,
    "hour_sin": 0.259,
    "hour_cos": 0.966,
    "is_zero_amount": 0,
    "is_high_amount": 0,
    "trans_num": "abc123"
}

response = requests.post(
    "http://localhost:8000/predict",
    json=features
)
print(response.json())
# {'is_fraud_predicted': 0, 'fraud_probability': 0.234, 'risk_level': 'LOW'}
```

---

## 📚 References

1. **Haversine Formula:** https://en.wikipedia.org/wiki/Haversine_formula
2. **Cyclic Encoding:** https://ianlondon.github.io/blog/encoding-cyclical-features-24hour-time/
3. **Sparkov Dataset:** https://www.kaggle.com/datasets/kartik2112/fraud-detection
4. **Project Spec:** `docs/PROJECT_SPECIFICATION.md`

---

**Version:** 2.0.0  
**Last Updated:** November 27, 2024  
**Maintained by:** Data Engineering Team
