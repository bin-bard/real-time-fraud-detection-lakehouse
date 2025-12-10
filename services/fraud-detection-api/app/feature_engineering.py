"""
Feature Engineering Module - Transform raw transaction data to ML features
Tất cả logic tính toán features (log, sin/cos, binning...) nằm ở đây
Chatbot chỉ cần gửi raw data, API tự tính toán
"""

import math
from typing import Dict, Any, Optional
from datetime import datetime
import pandas as pd


def engineer_features(
    amt: float,
    hour: Optional[int] = None,
    distance_km: Optional[float] = None,
    merchant: Optional[str] = None,
    category: Optional[str] = None,
    age: Optional[int] = None,
    gender: Optional[str] = None,
    day_of_week: Optional[int] = None,
    trans_num: Optional[str] = None
) -> Dict[str, Any]:
    """
    Transform raw transaction data to engineered features
    
    Args:
        amt: Transaction amount (required)
        hour: Hour of day (0-23), default = 12
        distance_km: Distance from customer home (km), default = 10.0
        merchant: Merchant name (optional)
        category: Transaction category (optional)
        age: Customer age, default = 35
        gender: Customer gender ('M'/'F'), default = 'M'
        day_of_week: Day of week (0=Monday, 6=Sunday), default = 0
        trans_num: Transaction ID, auto-generated if not provided
    
    Returns:
        Dictionary of engineered features ready for model prediction
    """
    
    # Set defaults
    hour = hour if hour is not None else 12
    distance_km = distance_km if distance_km is not None else 10.0
    age = age if age is not None else 35
    gender = gender if gender is not None else 'M'
    day_of_week = day_of_week if day_of_week is not None else 0
    
    if trans_num is None:
        trans_num = f"API_{pd.Timestamp.now():%Y%m%d%H%M%S}"
    
    # === AMOUNT FEATURES ===
    log_amount = math.log1p(amt)  # log(1 + amt) to handle 0
    is_zero_amount = 1 if amt == 0 else 0
    is_high_amount = 1 if amt > 500 else 0
    
    # Amount binning (risk levels by amount range)
    if amt == 0:
        amount_bin = 0
    elif amt <= 100:
        amount_bin = 1
    elif amt <= 300:
        amount_bin = 2
    elif amt <= 500:
        amount_bin = 3
    elif amt <= 1000:
        amount_bin = 4
    else:
        amount_bin = 5  # Very high amount
    
    # === GEOGRAPHIC FEATURES ===
    is_distant_transaction = 1 if distance_km > 50 else 0
    
    # === TIME FEATURES ===
    # Cyclic encoding for hour (sin/cos to capture periodicity)
    hour_sin = math.sin(2 * math.pi * hour / 24)
    hour_cos = math.cos(2 * math.pi * hour / 24)
    
    # Time-based flags
    is_weekend = 1 if day_of_week >= 5 else 0  # Saturday=5, Sunday=6
    is_late_night = 1 if (hour < 6 or hour >= 23) else 0
    
    # === DEMOGRAPHIC FEATURES ===
    gender_encoded = 0 if gender.upper() == 'M' else 1  # M=0, F=1
    
    # Return all features
    return {
        # Original raw values (for logging/explanation)
        "amt": amt,
        "hour": hour,
        "distance_km": distance_km,
        "age": age,
        "merchant": merchant,
        "category": category,
        "trans_num": trans_num,
        
        # Engineered features (for model)
        "log_amount": log_amount,
        "amount_bin": amount_bin,
        "is_zero_amount": is_zero_amount,
        "is_high_amount": is_high_amount,
        "is_distant_transaction": is_distant_transaction,
        "gender_encoded": gender_encoded,
        "day_of_week": day_of_week,
        "is_weekend": is_weekend,
        "is_late_night": is_late_night,
        "hour_sin": hour_sin,
        "hour_cos": hour_cos
    }


def get_feature_values_for_model(features: Dict[str, Any]) -> list:
    """
    Extract features in the correct order for ML model
    Model expects: [amt, log_amount, amount_bin, is_zero, is_high, distance_km, 
                    is_distant, age, gender, hour, dow, weekend, late_night, hour_sin, hour_cos]
    """
    return [
        features["amt"],
        features["log_amount"],
        features["amount_bin"],
        features["is_zero_amount"],
        features["is_high_amount"],
        features["distance_km"],
        features["is_distant_transaction"],
        features["age"],
        features["gender_encoded"],
        features["hour"],
        features["day_of_week"],
        features["is_weekend"],
        features["is_late_night"],
        features["hour_sin"],
        features["hour_cos"],
    ]


def explain_features(features: Dict[str, Any]) -> str:
    """Generate human-readable explanation of features"""
    explanations = []
    
    if features["is_high_amount"]:
        explanations.append(f"Giao dịch có giá trị cao (${features['amt']:.2f})")
    
    if features["is_distant_transaction"]:
        explanations.append(f"Giao dịch xa {features['distance_km']:.1f}km từ địa chỉ khách hàng")
    
    if features["is_late_night"]:
        explanations.append(f"Giao dịch vào lúc {features['hour']}h (đêm khuya/sáng sớm)")
    
    if features["is_weekend"]:
        explanations.append("Giao dịch vào cuối tuần")
    
    if features["amount_bin"] >= 5:
        explanations.append("Nằm trong khoảng giá trị rất cao (>$1000)")
    
    return "\n".join([f"- {e}" for e in explanations]) if explanations else "Không có đặc điểm bất thường nổi bật"


# Default feature templates for different scenarios
FEATURE_TEMPLATES = {
    "normal": {
        "amt": 50.0,
        "hour": 14,
        "distance_km": 5.0,
        "age": 35,
    },
    "high_risk": {
        "amt": 1500.0,
        "hour": 2,
        "distance_km": 150.0,
        "age": 22,
    },
    "suspicious": {
        "amt": 0.0,
        "hour": 3,
        "distance_km": 200.0,
        "age": 18,
    }
}


if __name__ == "__main__":
    # Test feature engineering
    print("=== TEST FEATURE ENGINEERING ===\n")
    
    # Test 1: Normal transaction
    print("1. Normal transaction:")
    normal_features = engineer_features(amt=50.0, hour=14, distance_km=5.0)
    print(f"   Amount bin: {normal_features['amount_bin']}")
    print(f"   Is high amount: {normal_features['is_high_amount']}")
    print(f"   Is late night: {normal_features['is_late_night']}")
    print(f"   Feature vector: {get_feature_values_for_model(normal_features)[:5]}...")
    
    # Test 2: Suspicious transaction
    print("\n2. Suspicious transaction:")
    sus_features = engineer_features(amt=1500.0, hour=2, distance_km=150.0, age=22)
    print(f"   Amount bin: {sus_features['amount_bin']}")
    print(f"   Is high amount: {sus_features['is_high_amount']}")
    print(f"   Is late night: {sus_features['is_late_night']}")
    print(f"   Is distant: {sus_features['is_distant_transaction']}")
    print(f"\n   Explanation:\n{explain_features(sus_features)}")
