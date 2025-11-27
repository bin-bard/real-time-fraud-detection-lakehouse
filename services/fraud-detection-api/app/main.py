from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
import numpy as np
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Fraud Detection API",
    description="Real-time fraud detection service for credit card transactions using Sparkov dataset",
    version="2.0.0"
)

# Input schema for Sparkov features
class TransactionFeatures(BaseModel):
    """
    Features từ Silver layer để predict fraud
    Bao gồm các features đã được engineer từ Sparkov dataset
    """
    # Transaction features
    amt: float
    log_amount: float
    amount_bin: int
    is_zero_amount: int
    is_high_amount: int
    
    # Geographic features
    distance_km: float
    is_distant_transaction: int
    
    # Demographic features
    age: int
    gender_encoded: int
    
    # Time features
    hour: int
    day_of_week: int
    is_weekend: int
    is_late_night: int
    hour_sin: float
    hour_cos: float
    
    # Optional: transaction metadata for logging
    trans_num: Optional[str] = None
    merchant: Optional[str] = None
    category: Optional[str] = None

class PredictionResponse(BaseModel):
    """Response model for fraud prediction"""
    trans_num: Optional[str]
    is_fraud_predicted: int  # 0 or 1
    fraud_probability: float  # 0.0 to 1.0
    risk_level: str  # LOW, MEDIUM, HIGH
    model_version: str

@app.get("/")
def read_root():
    return {
        "message": "Fraud Detection API - Sparkov Dataset",
        "version": "2.0.0",
        "status": "active",
        "endpoints": {
            "health": "/health",
            "predict": "/predict",
            "model_info": "/model/info"
        }
    }

@app.get('/health')
def health():
    return {
        "status": "healthy",
        "service": "fraud-detection-api",
        "model_loaded": False,  # Will be True when MLflow model is loaded
        "version": "2.0.0"
    }

@app.post("/predict", response_model=PredictionResponse)
async def predict_fraud(features: TransactionFeatures):
    """
    Predict fraud cho một transaction dựa trên features
    
    TODO: Load model từ MLflow và thực hiện prediction thực tế
    Hiện tại: Rule-based prediction để test
    """
    try:
        # TEMPORARY: Rule-based prediction
        # Sẽ thay thế bằng ML model từ MLflow
        
        # Simple rule-based scoring
        risk_score = 0.0
        
        # High amount increases risk
        if features.amt > 500:
            risk_score += 0.3
        
        # Long distance transaction
        if features.distance_km > 100:
            risk_score += 0.25
        
        # Late night transaction
        if features.is_late_night == 1:
            risk_score += 0.15
        
        # Distant transaction flag
        if features.is_distant_transaction == 1:
            risk_score += 0.2
        
        # Weekend transaction
        if features.is_weekend == 1:
            risk_score += 0.1
        
        # Cap at 1.0
        fraud_probability = min(risk_score, 1.0)
        
        # Classify
        is_fraud = 1 if fraud_probability > 0.5 else 0
        
        # Determine risk level
        if fraud_probability > 0.7:
            risk_level = "HIGH"
        elif fraud_probability > 0.4:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"
        
        logger.info(f"Prediction for {features.trans_num}: fraud={is_fraud}, prob={fraud_probability:.3f}, risk={risk_level}")
        
        return PredictionResponse(
            trans_num=features.trans_num,
            is_fraud_predicted=is_fraud,
            fraud_probability=round(fraud_probability, 4),
            risk_level=risk_level,
            model_version="rule_based_v1"  # Will change to MLflow model version
        )
        
    except Exception as e:
        logger.error(f"Error during prediction: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Prediction error: {str(e)}")

@app.get("/model/info")
def model_info():
    """
    Thông tin về model đang sử dụng
    """
    return {
        "model_type": "rule_based",  # Will be "random_forest" or "logistic_regression"
        "model_version": "1.0.0",
        "framework": "sklearn",  # Will be from MLflow
        "features_count": 15,
        "trained_on": "sparkov_dataset",
        "performance": {
            "auc": "N/A",  # Will be loaded from MLflow
            "accuracy": "N/A",
            "precision": "N/A",
            "recall": "N/A"
        },
        "status": "development"
    }

# To run locally for development: uvicorn app.main:app --host 0.0.0.0 --port 8000
