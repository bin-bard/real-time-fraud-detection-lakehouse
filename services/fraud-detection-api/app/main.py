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
from pyspark.sql import SparkSession
import pandas as pd

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# MLflow configuration
MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "http://mlflow:5000")
MODEL_NAME = os.getenv("MODEL_NAME", "fraud_detection_randomforest")
MODEL_STAGE = os.getenv("MODEL_STAGE", "None")  # Production, Staging, None

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
spark = None  # Global Spark session for PySpark models

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
    """Save prediction to fraud_predictions table"""
    try:
        conn = get_postgres_conn()
        if not conn:
            logger.warning("PostgreSQL connection not available, skipping save")
            return False
            
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO fraud_predictions (trans_num, prediction_score, is_fraud_predicted, model_version)
            VALUES (%s, %s, %s, %s)
        """, (trans_num, probability, prediction, model_ver))
        conn.commit()
        cur.close()
        conn.close()
        logger.info(f"✅ Saved prediction for {trans_num}")
        return True
    except Exception as e:
        logger.error(f"Failed to save prediction: {e}")
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
            explanation = f"{base}\n\n**Lý do phát hiện:**\n• " + "\n• ".join(reasons)
        else:
            explanation = f"{base}\n\nModel phát hiện các đặc trưng bất thường trong giao dịch này."
    else:  # Normal
        if probability > 0.3:
            explanation = f"⚡ **Giao dịch hợp lệ** (Nguy cơ gian lận: {probability:.1%})\n\nCó một số yếu tố cần lưu ý nhưng tổng thể giao dịch an toàn."
        else:
            explanation = f"✅ **Giao dịch an toàn** (Nguy cơ gian lận: {probability:.1%})\n\nCác đặc điểm giao dịch nằm trong mức bình thường."
    
    # Add transaction details
    details = f"\n\n**Chi tiết giao dịch:**\n"
    details += f"• Số tiền: ${features.amt:.2f}\n"
    details += f"• Khoảng cách: {features.distance_km:.1f}km\n"
    details += f"• Thời gian: {features.hour}h, {'cuối tuần' if features.is_weekend else 'ngày thường'}\n"
    details += f"• Tuổi khách hàng: {features.age} tuổi\n"
    if features.merchant:
        details += f"• Merchant: {features.merchant}\n"
    if features.category:
        details += f"• Category: {features.category}\n"
    
    return explanation + details

def init_spark_session():
    """Initialize Spark session for PySpark models"""
    global spark
    
    if spark is None:
        try:
            spark = SparkSession.builder \
                .appName("FraudDetectionAPI") \
                .config("spark.driver.memory", "2g") \
                .config("spark.sql.shuffle.partitions", "4") \
                .config("spark.ui.enabled", "false") \
                .config("spark.hadoop.fs.s3a.endpoint", "http://minio:9000") \
                .config("spark.hadoop.fs.s3a.access.key", "minio") \
                .config("spark.hadoop.fs.s3a.secret.key", "minio123") \
                .config("spark.hadoop.fs.s3a.path.style.access", "true") \
                .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem") \
                .getOrCreate()
            
            spark.sparkContext.setLogLevel("ERROR")
            logger.info("✅ Spark session initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize Spark: {e}")
            spark = None
    
    return spark

def load_model_from_mlflow():
    """Load latest model from MLflow"""
    global loaded_model, model_version, model_info
    
    try:
        # Initialize Spark session first (required for PySpark models)
        init_spark_session()
        
        client = MlflowClient()
        
        # Try to load from Model Registry first
        try:
            if MODEL_STAGE != "None":
                model_uri = f"models:/{MODEL_NAME}/{MODEL_STAGE}"
                logger.info(f"Loading model from Registry: {model_uri}")
            else:
                # Get latest version
                versions = client.search_model_versions(f"name='{MODEL_NAME}'")
                if versions:
                    latest_version = max(versions, key=lambda x: int(x.version))
                    model_uri = f"models:/{MODEL_NAME}/{latest_version.version}"
                    model_version = latest_version.version
                    logger.info(f"Loading model version {model_version}")
                else:
                    raise Exception("No registered models found")
            
            # Try loading as pyfunc first
            try:
                loaded_model = mlflow.pyfunc.load_model(model_uri)
                logger.info("✅ Model loaded successfully from Model Registry (pyfunc)")
            except Exception as pyfunc_error:
                logger.warning(f"PyFunc load failed: {pyfunc_error}")
                # Try loading as spark model directly
                logger.info("Trying to load as Spark model...")
                loaded_model = mlflow.spark.load_model(model_uri)
                logger.info("✅ Model loaded successfully from Model Registry (spark)")
            
        except Exception as e:
            # Fallback: Load latest run from experiment
            logger.warning(f"Model Registry load failed: {e}")
            logger.info("Trying to load from latest experiment run...")
            
            experiment = client.get_experiment_by_name("fraud_detection_production")
            if not experiment:
                raise Exception("Experiment 'fraud_detection_production' not found")
            
            runs = client.search_runs(
                experiment_ids=[experiment.experiment_id],
                filter_string="tags.model_type='RandomForest'",
                order_by=["start_time DESC"],
                max_results=1
            )
            
            if not runs:
                raise Exception("No training runs found")
            
            run = runs[0]
            model_uri = f"runs:/{run.info.run_id}/model"
            loaded_model = mlflow.pyfunc.load_model(model_uri)
            model_version = run.info.run_id[:8]
            
            # Get metrics
            model_info = {
                "run_id": run.info.run_id,
                "accuracy": run.data.metrics.get("accuracy", 0),
                "precision": run.data.metrics.get("precision", 0),
                "recall": run.data.metrics.get("recall", 0),
                "f1_score": run.data.metrics.get("f1_score", 0),
                "auc": run.data.metrics.get("auc", 0)
            }
            
            logger.info(f"✅ Model loaded from run {model_version}")
        
        return True
        
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
                # Prepare input data - support both Spark and sklearn models
                feature_dict = {
                    "amt": features.amt,
                    "log_amount": features.log_amount,
                    "is_zero_amount": features.is_zero_amount,
                    "is_high_amount": features.is_high_amount,
                    "amount_bin": features.amount_bin,
                    "distance_km": features.distance_km,
                    "is_distant_transaction": features.is_distant_transaction,
                    "age": features.age,
                    "gender_encoded": features.gender_encoded,
                    "hour": features.hour,
                    "day_of_week": features.day_of_week,
                    "is_weekend": features.is_weekend,
                    "is_late_night": features.is_late_night,
                    "hour_sin": features.hour_sin,
                    "hour_cos": features.hour_cos,
                }
                
                # Try Spark model first (if spark is initialized)
                if spark is not None and hasattr(loaded_model, 'transform'):
                    # Spark model - use DataFrame
                    df = spark.createDataFrame([feature_dict])
                    predictions = loaded_model.transform(df)
                    result = predictions.select("prediction", "probability").collect()[0]
                    is_fraud = int(result["prediction"])
                    fraud_probability = float(result["probability"][1])  # Probability of class 1
                else:
                    # PyFunc model - use pandas DataFrame (safer than numpy for MLflow)
                    input_df = pd.DataFrame([feature_dict])
                    prediction = loaded_model.predict(input_df)
                    is_fraud = int(prediction[0])
                    
                    # Try to get probability
                    try:
                        proba = loaded_model.predict_proba(input_df)
                        fraud_probability = float(proba[0][1]) if len(proba[0]) > 1 else float(is_fraud)
                    except:
                        fraud_probability = float(is_fraud)
                
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
    """
    try:
        if loaded_model is None:
            # Fallback to rule-based
            logger.info("⚠️ Model chưa train, sử dụng rule-based prediction")
            is_fraud, fraud_probability = rule_based_prediction(features)
            model_ver = "rule_based_v1.0"
        else:
            # Use MLflow model
            feature_array = np.array([[
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
                0.0, 0.0, 0.0, 0.0, 0.0  # Placeholders
            ]])
            
            try:
                prediction = loaded_model.predict(feature_array)
                is_fraud = int(prediction[0])
                
                try:
                    proba = loaded_model.predict_proba(feature_array)
                    fraud_probability = float(proba[0][1]) if len(proba[0]) > 1 else float(is_fraud)
                except:
                    fraud_probability = float(is_fraud)
                
                model_ver = f"mlflow_{model_version}"
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
                "features_used": 20,
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
            "features_count": 20,
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
