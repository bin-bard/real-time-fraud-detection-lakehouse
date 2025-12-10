from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
import numpy as np
import logging
import mlflow
import os
from datetime import datetime
from mlflow.tracking import MlflowClient
import psycopg2
from psycopg2.extras import RealDictCursor

# Import feature engineering
from app.feature_engineering import engineer_features, get_feature_values_for_model, explain_features

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# MLflow configuration
MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "http://mlflow:5000")
MODEL_NAME = os.getenv("MODEL_NAME", "sklearn_fraud_randomforest")
MODEL_STAGE = os.getenv("MODEL_STAGE", "Production")  # Production, Staging, None

mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)

# PostgreSQL configuration for saving predictions
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "postgres")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB = os.getenv("POSTGRES_DB", "frauddb")
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")

# Global model variable
loaded_model = None
model_version = None
model_info = {}

# Input schema for Sparkov features - ĐỊNH NGHĨA TRƯỚC
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


# NEW: Raw transaction input (chatbot chỉ cần gửi raw data)
class RawTransactionInput(BaseModel):
    """
    Raw transaction data from chatbot/user
    API sẽ tự động tính toán các features cần thiết
    """
    # Required
    amt: float  # Transaction amount
    
    # Optional (có defaults)
    hour: Optional[int] = None  # Hour of day (0-23)
    distance_km: Optional[float] = None  # Distance from home (km)
    merchant: Optional[str] = None  # Merchant name
    category: Optional[str] = None  # Transaction category
    age: Optional[int] = None  # Customer age
    gender: Optional[str] = None  # 'M' or 'F'
    day_of_week: Optional[int] = None  # 0=Monday, 6=Sunday
    trans_num: Optional[str] = None  # Transaction ID (auto-generated if not provided)

def get_postgres_conn():
    """Get PostgreSQL connection"""
    try:
        return psycopg2.connect(
            host=POSTGRES_HOST,
            port=POSTGRES_PORT,
            database=POSTGRES_DB,
            user=POSTGRES_USER,
            password=POSTGRES_PASSWORD
        )
    except Exception as e:
        logger.error(f"Failed to connect to PostgreSQL: {e}")
        return None

def save_prediction_to_db(trans_num: str, prediction: int, probability: float, model_ver: str):
    """
    Save prediction to fraud_predictions table
    NOTE: Chỉ lưu REAL-TIME predictions từ Kafka/Bronze streaming.
    - Chatbot/Manual predictions (CHAT_*, MANUAL_*) KHÔNG lưu vì không có transaction record
    - Foreign key constraint: fraud_predictions.trans_num -> transactions.trans_num
    - Real-time từ Kafka sẽ có transaction record trước khi predict
    """
    # Skip saving for chatbot/manual predictions
    if trans_num.startswith(('CHAT_', 'MANUAL_')):
        logger.info(f"⏭️ Skipping DB save for manual/chatbot prediction: {trans_num}")
        return True
    
    # Skip saving if using rule-based fallback
    if "rule_based" in model_ver.lower() or "fallback" in model_ver.lower():
        logger.info(f"⏭️ Skipping DB save for rule-based prediction: {trans_num}")
        return True
    
    try:
        conn = get_postgres_conn()
        if not conn:
            logger.error("❌ PostgreSQL connection failed - Prediction NOT saved!")
            return False
            
        cur = conn.cursor()
        
        # INSERT with ON CONFLICT to handle duplicates
        insert_sql = """
            INSERT INTO fraud_predictions (trans_num, prediction_score, is_fraud_predicted, model_version, prediction_time)
            VALUES (%s, %s, %s, %s, NOW())
            ON CONFLICT (trans_num) 
            DO UPDATE SET 
                prediction_score = EXCLUDED.prediction_score,
                is_fraud_predicted = EXCLUDED.is_fraud_predicted,
                model_version = EXCLUDED.model_version,
                prediction_time = NOW()
        """
        
        cur.execute(insert_sql, (trans_num, float(probability), int(prediction), model_ver))
        conn.commit()
        cur.close()
        conn.close()
        logger.info(f"✅ Saved prediction for {trans_num}")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to save prediction: {str(e)}")
        return False
        return False

def explain_prediction(features: TransactionFeatures, prediction: int, probability: float) -> str:
    """Generate natural language explanation in Vietnamese"""
    reasons = []
    
    # Amount analysis
    if features.is_high_amount:
        reasons.append(f"giao dịch có giá trị cao (${features.amt:.2f})")
    elif features.amt > 300:
        reasons.append(f"giao dịch có giá trị khá lớn (${features.amt:.2f})")
    if features.is_zero_amount:
        reasons.append("giao dịch có giá trị $0 (rất đáng ngờ)")
    
    # Distance analysis
    if features.is_distant_transaction:
        reasons.append(f"giao dịch xa {features.distance_km:.1f}km từ địa chỉ khách hàng")
    elif features.distance_km > 50:
        reasons.append(f"khoảng cách {features.distance_km:.1f}km khá xa")
    
    # Time analysis
    if features.is_late_night:
        reasons.append(f"giao dịch vào lúc {features.hour}h (đêm khuya/sáng sớm)")
    if features.is_weekend:
        reasons.append("giao dịch vào cuối tuần")
    
    # Amount bin risk
    if features.amount_bin >= 5:
        reasons.append("nằm trong khoảng giá trị có nguy cơ gian lận rất cao (>$1000)")
    elif features.amount_bin >= 4:
        reasons.append("nằm trong khoảng giá trị có nguy cơ gian lận cao (>$500)")
    
    # Build explanation
    if prediction == 1:  # Fraud
        base = f"⚠️ **CẢNH BÁO GIAN LẬN** (Xác suất: {probability:.1%})"
        if reasons:
            # Format reasons with proper spacing
            formatted_reasons = "\n".join([f"- {reason}" for reason in reasons])
            explanation = f"{base}\n\n**Lý do phát hiện:**\n\n{formatted_reasons}"
        else:
            explanation = f"{base}\n\nModel phát hiện các đặc trưng bất thường trong giao dịch này."
    else:  # Normal
        if probability > 0.3:
            explanation = f"⚡ **Giao dịch hợp lệ** (Nguy cơ gian lận: {probability:.1%})\n\nCó một số yếu tố cần lưu ý nhưng tổng thể giao dịch an toàn."
        else:
            explanation = f"✅ **Giao dịch an toàn** (Nguy cơ gian lận: {probability:.1%})\n\nCác đặc điểm giao dịch nằm trong mức bình thường."
    
    # Add transaction details with proper spacing
    details = f"\n\n**Chi tiết giao dịch:**\n\n"
    details += f"- Số tiền: ${features.amt:.2f}\n"
    details += f"- Khoảng cách: {features.distance_km:.1f}km\n"
    details += f"- Thời gian: {features.hour}h, {'cuối tuần' if features.is_weekend else 'ngày thường'}\n"
    details += f"- Tuổi khách hàng: {features.age} tuổi\n"
    if features.merchant:
        details += f"- Merchant: {features.merchant}\n"
    if features.category:
        details += f"- Category: {features.category}\n"
    
    return explanation + details

def load_model_from_mlflow():
    """
    Load sklearn model from MLflow (much simpler than PySpark!)
    """
    global loaded_model, model_version, model_info
    
    try:
        
        client = MlflowClient()
        
        # Get Production model version
        try:
            if MODEL_STAGE == "Production":
                versions = client.search_model_versions(f"name='{MODEL_NAME}'")
                prod_versions = [v for v in versions if v.current_stage == "Production"]
                
                if prod_versions:
                    latest_prod = max(prod_versions, key=lambda x: int(x.version))
                    run_id = latest_prod.run_id
                    model_version = latest_prod.version
                    logger.info(f"Found Production model: v{model_version}, run_id={run_id}")
                else:
                    raise Exception("No Production model found")
            else:
                # Get latest version
                versions = client.search_model_versions(f"name='{MODEL_NAME}'")
                if versions:
                    latest_version = max(versions, key=lambda x: int(x.version))
                    run_id = latest_version.run_id
                    model_version = latest_version.version
                    logger.info(f"Found latest model: v{model_version}, run_id={run_id}")
                else:
                    raise Exception("No model versions found")
            
            # Load sklearn model directly from MLflow (simple!)
            model_uri = f"runs:/{run_id}/model"
            logger.info(f"📥 Loading sklearn model: {model_uri}")
            
            # sklearn models load easily with mlflow.sklearn or mlflow.pyfunc
            loaded_model = mlflow.sklearn.load_model(model_uri)
            
            logger.info(f"✅ Sklearn model loaded successfully: {MODEL_NAME} v{model_version}")
            
            # Get model metrics
            try:
                run_data = client.get_run(run_id)
                model_info = {
                    "model_name": MODEL_NAME,
                    "model_version": model_version,
                    "run_id": run_id,
                    "accuracy": run_data.data.metrics.get("accuracy", 0),
                    "precision": run_data.data.metrics.get("precision", 0),
                    "recall": run_data.data.metrics.get("recall", 0),
                    "f1_score": run_data.data.metrics.get("f1_score", 0),
                    "auc": run_data.data.metrics.get("auc", 0)
                }
                logger.info(f"📊 Model metrics: Acc={model_info['accuracy']:.3f}, F1={model_info['f1_score']:.3f}, AUC={model_info['auc']:.3f}")
            except Exception as info_error:
                logger.warning(f"Could not fetch model metrics: {info_error}")
                model_info = {"model_name": MODEL_NAME, "model_version": model_version, "run_id": run_id}
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Model load failed: {e}")
            logger.info("Will use rule-based prediction as fallback")
            return False
        
    except Exception as e:
        logger.error(f"❌ Failed to load model from MLflow: {e}")
        logger.info("Will use rule-based prediction as fallback")
        return False

app = FastAPI(
    title="Fraud Detection API",
    description="Real-time fraud detection service using MLflow models",
    version="3.0.0"
)

# Load model on startup
@app.on_event("startup")
async def startup_event():
    logger.info("Starting Fraud Detection API...")
    load_model_from_mlflow()

class PredictionResponse(BaseModel):
    """Response model for fraud prediction"""
    trans_num: Optional[str]
    is_fraud_predicted: int  # 0 or 1
    fraud_probability: float  # 0.0 to 1.0
    risk_level: str  # LOW, MEDIUM, HIGH
    model_version: str

class PredictionResponseExtended(BaseModel):
    """Extended response with natural language explanation"""
    trans_num: Optional[str]
    is_fraud_predicted: int
    fraud_probability: float
    risk_level: str
    model_version: str
    explanation: str  # Natural language explanation in Vietnamese
    model_info: dict  # Model parameters and metrics
    timestamp: datetime
    saved_to_db: bool

@app.get("/")
def read_root():
    return {
        "message": "Fraud Detection API - MLflow Integrated",
        "version": "3.0.0",
        "status": "active",
        "model_loaded": loaded_model is not None,
        "model_version": model_version if model_version else "N/A",
            "endpoints": {
            "health": "/health",
            "predict": "/predict",
            "predict_explained": "/predict/explained",
            "predict_batch": "/predict/batch",
            "model_info": "/model/info",
            "reload_model": "/model/reload",
            "prediction_history": "/predictions/history"
        }
    }

@app.get('/health')
def health():
    return {
        "status": "healthy",
        "service": "fraud-detection-api",
        "model_loaded": loaded_model is not None,
        "model_version": model_version if model_version else "N/A",
        "mlflow_uri": MLFLOW_TRACKING_URI,
        "version": "3.0.0"
    }

@app.post("/predict", response_model=PredictionResponse)
async def predict_fraud(features: TransactionFeatures):
    """
    Predict fraud for a single transaction using MLflow model
    """
    try:
        if loaded_model is not None:
            # Use MLflow model
            try:
                # Prepare input data - sklearn expects numpy array
                # IMPORTANT: Order MUST match training features in ml_training_sklearn.py
                feature_values = [
                    features.amt,
                    features.log_amount,
                    features.is_zero_amount,
                    features.is_high_amount,
                    features.amount_bin,
                    features.distance_km,
                    features.is_distant_transaction,
                    features.age,
                    features.gender_encoded,
                    features.hour,
                    features.day_of_week,
                    features.is_weekend,
                    features.is_late_night,
                    features.hour_sin,
                    features.hour_cos,
                ]
                
                # Reshape for sklearn (expects 2D array)
                X = np.array(feature_values).reshape(1, -1)
                
                # Debug logging
                logger.info(f"🔍 Prediction input: shape={X.shape}, features={len(feature_values)}")
                logger.debug(f"Feature values: amt={features.amt}, hour={features.hour}, distance={features.distance_km}")
                
                # Predict
                is_fraud = int(loaded_model.predict(X)[0])
                
                # Get probability if available
                try:
                    proba = loaded_model.predict_proba(X)[0]
                    fraud_probability = float(proba[1])  # Probability of fraud (class 1)
                except:
                    fraud_probability = float(is_fraud)  # Fallback to binary prediction
                
                model_ver = f"mlflow_{model_version}"
                logger.info(f"✅ MLflow prediction successful: fraud={is_fraud}, prob={fraud_probability:.3f}")
                
            except Exception as e:
                logger.error(f"MLflow prediction failed: {e}, using rule-based fallback")
                is_fraud, fraud_probability = rule_based_prediction(features)
                model_ver = "rule_based_fallback"
        else:
            # Fallback to rule-based
            logger.warning("Model not loaded, using rule-based prediction")
            is_fraud, fraud_probability = rule_based_prediction(features)
            model_ver = "rule_based_v1"
        
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
            model_version=model_ver
        )
        
    except Exception as e:
        logger.error(f"Error during prediction: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Prediction error: {str(e)}")

@app.post("/predict/explained", response_model=PredictionResponseExtended)
async def predict_with_explanation(features: TransactionFeatures):
    """
    🌟 Predict fraud với giải thích chi tiết bằng ngôn ngữ tự nhiên (Vietnamese)
    
    - Dự đoán gian lận dựa trên ML model (hoặc rule-based nếu model chưa train)
    - Giải thích lý do tại sao giao dịch bị đánh dấu gian lận
    - Lưu kết quả vào database
    - Cung cấp thông tin model (metrics, parameters)
    
    NOTE: Endpoint này trả về explanation text (Vietnamese) cho chatbot.
    Nếu chỉ cần kết quả ngắn gọn, dùng /predict endpoint.
    Gemini AI insights (nếu có) được thêm ở chatbot layer, không phải API này.
    """
    try:
        if loaded_model is None:
            # Fallback to rule-based
            logger.info("⚠️ Model chưa train, sử dụng rule-based prediction")
            is_fraud, fraud_probability = rule_based_prediction(features)
            model_ver = "rule_based_v1.0"
        else:
            # Use MLflow model - SAME as /predict endpoint
            try:
                # IMPORTANT: Order MUST match training features in ml_training_sklearn.py
                feature_values = [
                    features.amt,
                    features.log_amount,
                    features.is_zero_amount,
                    features.is_high_amount,
                    features.amount_bin,
                    features.distance_km,
                    features.is_distant_transaction,
                    features.age,
                    features.gender_encoded,
                    features.hour,
                    features.day_of_week,
                    features.is_weekend,
                    features.is_late_night,
                    features.hour_sin,
                    features.hour_cos,
                ]
                
                # Reshape for sklearn (expects 2D array)
                X = np.array(feature_values).reshape(1, -1)
                
                # Debug logging
                logger.info(f"🔍 Prediction input: shape={X.shape}, features={len(feature_values)}")
                
                # Predict
                is_fraud = int(loaded_model.predict(X)[0])
                
                # Get probability if available
                try:
                    proba = loaded_model.predict_proba(X)[0]
                    fraud_probability = float(proba[1])  # Probability of fraud (class 1)
                except:
                    fraud_probability = float(is_fraud)  # Fallback to binary prediction
                
                model_ver = f"mlflow_{model_version}"
                logger.info(f"✅ MLflow prediction successful: fraud={is_fraud}, prob={fraud_probability:.3f}")
                
            except Exception as e:
                logger.error(f"MLflow prediction failed: {e}, using rule-based fallback")
                is_fraud, fraud_probability = rule_based_prediction(features)
                model_ver = "rule_based_fallback"
        
        # Risk level
        if fraud_probability > 0.7:
            risk_level = "HIGH"
        elif fraud_probability > 0.4:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"
        
        # Generate explanation
        explanation = explain_prediction(features, is_fraud, fraud_probability)
        
        # Save to database
        saved = False
        if features.trans_num:
            saved = save_prediction_to_db(features.trans_num, is_fraud, fraud_probability, model_ver)
        
        # Get model info
        if loaded_model and model_info:
            model_info_data = {
                "model_type": "mlflow_model",
                "model_version": model_version,
                "framework": "sklearn_RandomForest",
                "features_used": 15,  # FIX: 15 features, not 20
                "training_metrics": {
                    "accuracy": round(model_info.get("accuracy", 0), 4),
                    "precision": round(model_info.get("precision", 0), 4),
                    "recall": round(model_info.get("recall", 0), 4),
                    "f1_score": round(model_info.get("f1_score", 0), 4),
                    "auc": round(model_info.get("auc", 0), 4)
                }
            }
        else:
            model_info_data = {
                "model_type": "rule_based",
                "model_version": "1.0",
                "framework": "custom_rules",
                "features_used": 5,
                "training_metrics": {
                    "note": "Rule-based system, no training metrics available"
                }
            }
        
        logger.info(f"✅ Prediction for {features.trans_num}: fraud={is_fraud}, prob={fraud_probability:.3f}, risk={risk_level}")
        
        return PredictionResponseExtended(
            trans_num=features.trans_num,
            is_fraud_predicted=is_fraud,
            fraud_probability=round(fraud_probability, 4),
            risk_level=risk_level,
            model_version=model_ver,
            explanation=explanation,
            model_info=model_info_data,
            timestamp=datetime.now(),
            saved_to_db=saved
        )
        
    except Exception as e:
        logger.error(f"Error during prediction: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Prediction error: {str(e)}")

@app.get("/predictions/history")
def get_prediction_history(limit: int = 50):
    """
    📊 Lấy lịch sử dự đoán từ database
    
    - limit: số lượng bản ghi tối đa (mặc định 50)
    """
    try:
        conn = get_postgres_conn()
        if not conn:
            return {"error": "PostgreSQL connection not available", "predictions": []}
            
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT 
                fp.trans_num,
                fp.prediction_score,
                fp.is_fraud_predicted,
                fp.model_version,
                fp.prediction_time,
                t.amt,
                t.merchant,
                t.category,
                t.is_fraud as actual_fraud
            FROM fraud_predictions fp
            LEFT JOIN transactions t ON fp.trans_num = t.trans_num
            ORDER BY fp.prediction_time DESC
            LIMIT %s
        """, (limit,))
        results = cur.fetchall()
        cur.close()
        conn.close()
        
        # Calculate accuracy if we have actual labels
        correct = sum(1 for r in results if r.get('actual_fraud') is not None and r['is_fraud_predicted'] == r['actual_fraud'])
        total_with_labels = sum(1 for r in results if r.get('actual_fraud') is not None)
        
        return {
            "predictions": results,
            "count": len(results),
            "accuracy": round(correct / total_with_labels * 100, 2) if total_with_labels > 0 else None,
            "total_with_labels": total_with_labels
        }
    except Exception as e:
        logger.error(f"Failed to fetch history: {e}")
        return {"error": str(e), "predictions": []}

def rule_based_prediction(features: TransactionFeatures):
    """Fallback rule-based prediction when MLflow model unavailable"""
    risk_score = 0.0
    
    if features.amt > 500:
        risk_score += 0.3
    if features.distance_km > 100:
        risk_score += 0.25
    if features.is_late_night == 1:
        risk_score += 0.15
    if features.is_distant_transaction == 1:
        risk_score += 0.2
    if features.is_weekend == 1:
        risk_score += 0.1
    
    fraud_probability = min(risk_score, 1.0)
    is_fraud = 1 if fraud_probability > 0.5 else 0
    
    return is_fraud, fraud_probability

@app.get("/model/info")
def model_info_endpoint():
    """Get current model information"""
    if loaded_model and model_info:
        return {
            "model_type": "mlflow_model",
            "model_name": MODEL_NAME,
            "model_version": model_version,
            "framework": "sklearn",
            "mlflow_tracking_uri": MLFLOW_TRACKING_URI,
            "features_count": 15,  # FIX: 15 features, not 20
            "trained_on": "sparkov_dataset",
            "performance": {
                "accuracy": model_info.get("accuracy", "N/A"),
                "precision": model_info.get("precision", "N/A"),
                "recall": model_info.get("recall", "N/A"),
                "f1_score": model_info.get("f1_score", "N/A"),
                "auc": model_info.get("auc", "N/A")
            },
            "status": "production_ready"
        }
    else:
        return {
            "model_type": "rule_based",
            "model_version": "1.0.0",
            "framework": "custom",
            "features_count": 15,
            "trained_on": "N/A",
            "performance": {
                "auc": "N/A",
                "accuracy": "N/A",
                "precision": "N/A",
                "recall": "N/A"
            },
            "status": "fallback_mode",
            "note": "MLflow model not loaded, using rule-based fallback"
        }

@app.post("/predict/raw")
async def predict_fraud_from_raw(raw_data: RawTransactionInput):
    """
    **NEW ENDPOINT: Predict fraud từ raw transaction data**
    
    Chatbot chỉ cần gửi dữ liệu thô (amt, hour, distance_km...),
    API tự động tính toán tất cả features cần thiết.
    
    Lợi ích:
    - Chatbot không cần biết về feature engineering
    - Có thể thay đổi model/features mà không sửa chatbot
    - Logic tính toán tập trung ở một nơi
    """
    try:
        # 1. Feature engineering (API tự tính toán)
        engineered = engineer_features(
            amt=raw_data.amt,
            hour=raw_data.hour,
            distance_km=raw_data.distance_km,
            merchant=raw_data.merchant,
            category=raw_data.category,
            age=raw_data.age,
            gender=raw_data.gender,
            day_of_week=raw_data.day_of_week,
            trans_num=raw_data.trans_num
        )
        
        logger.info(f"🔧 Engineered features for {engineered['trans_num']}: "
                   f"amt_bin={engineered['amount_bin']}, "
                   f"is_high_amt={engineered['is_high_amount']}, "
                   f"is_late_night={engineered['is_late_night']}")
        
        # 2. Convert to TransactionFeatures for prediction
        features = TransactionFeatures(
            amt=engineered["amt"],
            log_amount=engineered["log_amount"],
            amount_bin=engineered["amount_bin"],
            is_zero_amount=engineered["is_zero_amount"],
            is_high_amount=engineered["is_high_amount"],
            distance_km=engineered["distance_km"],
            is_distant_transaction=engineered["is_distant_transaction"],
            age=engineered["age"],
            gender_encoded=engineered["gender_encoded"],
            hour=engineered["hour"],
            day_of_week=engineered["day_of_week"],
            is_weekend=engineered["is_weekend"],
            is_late_night=engineered["is_late_night"],
            hour_sin=engineered["hour_sin"],
            hour_cos=engineered["hour_cos"],
            trans_num=engineered["trans_num"],
            merchant=engineered["merchant"],
            category=engineered["category"]
        )
        
        # 3. Use existing prediction logic
        result = await predict_fraud(features)
        
        # 4. Add feature explanation
        feature_explanation = explain_features(engineered)
        
        return {
            **result.dict(),
            "feature_explanation": feature_explanation,
            "raw_input": {
                "amt": raw_data.amt,
                "hour": raw_data.hour,
                "distance_km": raw_data.distance_km
            }
        }
        
    except Exception as e:
        logger.error(f"❌ Raw prediction error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Prediction error: {str(e)}")


@app.post("/model/reload")
def reload_model():
    """Reload model from MLflow (useful after retraining)"""
    try:
        success = load_model_from_mlflow()
        if success:
            return {
                "status": "success",
                "message": "Model reloaded successfully",
                "model_version": model_version,
                "model_loaded": loaded_model is not None
            }
        else:
            return {
                "status": "warning",
                "message": "Model reload attempted but using rule-based fallback",
                "model_loaded": False
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Reload failed: {str(e)}")

@app.post("/predict/batch")
async def predict_batch(transactions: list[TransactionFeatures]):
    """
    Batch prediction for multiple transactions
    Useful for processing accumulated transactions
    """
    try:
        results = []
        for features in transactions:
            pred = await predict_fraud(features)
            results.append(pred)
        
        # Summary statistics
        total = len(results)
        fraud_count = sum(1 for r in results if r.is_fraud_predicted == 1)
        high_risk = sum(1 for r in results if r.risk_level == "HIGH")
        
        return {
            "predictions": results,
            "summary": {
                "total_transactions": total,
                "fraud_detected": fraud_count,
                "fraud_rate": round(fraud_count / total * 100, 2) if total > 0 else 0,
                "high_risk_count": high_risk,
                "model_version": model_version if model_version else "rule_based_v1"
            }
        }
        
    except Exception as e:
        logger.error(f"Batch prediction error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Batch prediction error: {str(e)}")

# To run locally for development: uvicorn app.main:app --host 0.0.0.0 --port 8000
