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
    """Gọi batch prediction API"""
    try:
        response = requests.post(
            f"{FRAUD_API_URL}/predict/batch",
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
