"""
API Client for Fraud Detection API
Xử lý tất cả requests tới FastAPI backend
"""

import requests
import os
from typing import Dict, List

# FastAPI endpoint
FRAUD_API_URL = os.getenv("FRAUD_API_URL", "http://fraud-detection-api:8000")

def get_fraud_api_status() -> Dict:
    """Kiểm tra trạng thái Fraud Detection API"""
    try:
        response = requests.get(f"{FRAUD_API_URL}/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            return {
                "status": "healthy",
                "model_loaded": data.get("model_loaded", False),
                "model_version": data.get("model_version", "N/A")
            }
    except Exception as e:
        return {"status": "error", "message": str(e)}
    return {"status": "unknown"}

def predict_fraud_api(transaction_data: dict) -> Dict:
    """Gọi API để dự đoán fraud với giải thích LLM"""
    try:
        response = requests.post(
            f"{FRAUD_API_URL}/predict/explained",
            json=transaction_data,
            timeout=30  # Gemini có thể mất thời gian
        )
        response.raise_for_status()
        return {"success": True, "data": response.json()}
    except requests.exceptions.Timeout:
        return {"success": False, "error": "API timeout (>30s)"}
    except requests.exceptions.ConnectionError:
        return {"success": False, "error": "Không thể kết nối tới Fraud Detection API"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def predict_batch_api(transactions: List[dict]) -> Dict:
    """
    Gọi batch prediction API với RAW data
    API sẽ tự tính features cho từng transaction
    """
    try:
        response = requests.post(
            f"{FRAUD_API_URL}/predict/batch/raw",  # Changed: use /raw endpoint
            json=transactions,  # API expects list directly, not wrapped in {"transactions": ...}
            timeout=60
        )
        response.raise_for_status()
        return {"success": True, "data": response.json()}
    except requests.exceptions.Timeout:
        return {"success": False, "error": "Batch API timeout (>60s)"}
    except requests.exceptions.ConnectionError:
        return {"success": False, "error": "Không thể kết nối tới Fraud Detection API"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def get_model_info() -> Dict:
    """Lấy thông tin model từ API"""
    try:
        response = requests.get(f"{FRAUD_API_URL}/model/info", timeout=5)
        response.raise_for_status()
        return {"success": True, "data": response.json()}
    except Exception as e:
        return {"success": False, "error": str(e)}

def get_prediction_history(limit: int = 10) -> Dict:
    """Lấy lịch sử predictions từ API"""
    try:
        response = requests.get(
            f"{FRAUD_API_URL}/predictions/history?limit={limit}", 
            timeout=10
        )
        response.raise_for_status()
        return {"success": True, "data": response.json()}
    except Exception as e:
        return {"success": False, "error": str(e)}


def predict_fraud_raw(
    amt: float,
    hour: int = None,
    distance_km: float = None,
    merchant: str = None,
    category: str = None,
    age: int = None
) -> Dict:
    """
    **NEW: Dự đoán fraud với raw data (KHUYẾN NGHỊ)**
    
    Chatbot chỉ cần gửi dữ liệu thô, API tự tính toán features.
    Tách biệt logic feature engineering khỏi chatbot.
    
    Args:
        amt: Số tiền giao dịch (bắt buộc)
        hour: Giờ giao dịch (0-23)
        distance_km: Khoảng cách từ nhà (km)
        merchant: Tên merchant
        category: Loại giao dịch
        age: Tuổi khách hàng
    
    Returns:
        {
            "success": True/False,
            "data": {prediction result} or None,
            "error": error message if failed
        }
    """
    try:
        # Build payload with only provided fields
        payload = {"amt": amt}
        
        if hour is not None:
            payload["hour"] = hour
        if distance_km is not None:
            payload["distance_km"] = distance_km
        if merchant:
            payload["merchant"] = merchant
        if category:
            payload["category"] = category
        if age is not None:
            payload["age"] = age
        
        response = requests.post(
            f"{FRAUD_API_URL}/predict/raw",
            json=payload,
            timeout=15
        )
        response.raise_for_status()
        return {"success": True, "data": response.json()}
        
    except requests.exceptions.Timeout:
        return {"success": False, "error": "API timeout (>15s)"}
    except requests.exceptions.ConnectionError:
        return {"success": False, "error": "Không thể kết nối tới Fraud Detection API"}
    except Exception as e:
        return {"success": False, "error": str(e)}

