from pyspark.sql import SparkSession
from pyspark.sql.functions import col, when, lit, isnan, isnull
from pyspark.sql.types import DoubleType, IntegerType
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import MinMaxScaler
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, roc_auc_score, confusion_matrix
import mlflow
import mlflow.sklearn
from mlflow.tracking import MlflowClient
import logging
import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime

# Configure MLflow S3 artifact storage
os.environ["AWS_ACCESS_KEY_ID"] = "minio"
os.environ["AWS_SECRET_ACCESS_KEY"] = "minio123"
os.environ["MLFLOW_S3_ENDPOINT_URL"] = "http://minio:9000"
os.environ["GIT_PYTHON_REFRESH"] = "quiet"

# MLflow configuration
mlflow.set_tracking_uri("http://mlflow:5000")
mlflow.set_experiment("fraud_detection_sklearn")

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

def log_step(step_name, message):
    """Log with step prefix"""
    full_message = f"[STEP: {step_name}] {message}"
    logger.info(full_message)
    sys.stdout.flush()

def create_spark_session():
    """Initialize Spark Session with Delta Lake"""
    return SparkSession.builder \
        .appName("SklearnFraudTraining") \
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
        .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog") \
        .config("spark.hadoop.fs.s3a.endpoint", "http://minio:9000") \
        .config("spark.hadoop.fs.s3a.access.key", "minio") \
        .config("spark.hadoop.fs.s3a.secret.key", "minio123") \
        .config("spark.hadoop.fs.s3a.path.style.access", "true") \
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem") \
        .getOrCreate()

def prepare_features(df):
    """
    Feature engineering - GIỐNG ml_training_job.py
    """
    log_step("FEATURE_PREP", "🔧 Preparing features for ML training...")
    
    # IMPORTANT: These features MUST exist in Silver layer
    feature_cols = [
        # Transaction amount features (from silver_job.py)
        "amt", "log_amount", "is_zero_amount", "is_high_amount", "amount_bin",
        
        # Geographic features (from silver_job.py)
        "distance_km", "is_distant_transaction",
        
        # Demographic features (from silver_job.py)
        "age", "gender_encoded",
        
        # Time features (from silver_job.py)
        "hour", "day_of_week", "is_weekend", "is_late_night",
        "hour_sin", "hour_cos"
    ]
    
    # Check available columns and warn if missing
    available_features = [f for f in feature_cols if f in df.columns]
    missing_features = [f for f in feature_cols if f not in df.columns]
    
    if missing_features:
        log_step("FEATURE_PREP", f"⚠️ WARNING: Missing features from Silver layer: {missing_features}")
        log_step("FEATURE_PREP", "These features will be skipped from training")
    
    log_step("FEATURE_PREP", f"📌 Using {len(available_features)}/{len(feature_cols)} features")
    log_step("FEATURE_PREP", f"Features: {', '.join(available_features[:10])}{'...' if len(available_features) > 10 else ''}")
    
    # Fill missing values with median (Kaggle approach)
    log_step("FEATURE_PREP", "Filling missing values with median...")
    for feat in available_features:
        # Get median value
        median_vals = df.filter(col(feat).isNotNull() & ~isnan(col(feat))) \
                        .approxQuantile(feat, [0.5], 0.01)
        median_val = median_vals[0] if median_vals else 0.0
        
        df = df.withColumn(
            feat,
            when(col(feat).isNull() | isnan(col(feat)), lit(median_val))
            .otherwise(col(feat).cast(DoubleType()))
        )
    
    log_step("FEATURE_PREP", "✅ Feature preparation complete")
    return df, available_features

def handle_class_imbalance(df, label_col="is_fraud"):
    """
    Handle imbalanced data - GIỐNG ml_training_job.py
    Undersample majority class to balance dataset
    """
    log_step("CLASS_BALANCE", "⚖️ Handling class imbalance...")
    
    # Count fraud and non-fraud
    fraud_df = df.filter(col(label_col) == 1).cache()
    nonfraud_df = df.filter(col(label_col) == 0)
    
    fraud_count = fraud_df.count()
    nonfraud_count = nonfraud_df.count()
    
    log_step("CLASS_BALANCE", f"Original distribution: Fraud={fraud_count}, Non-Fraud={nonfraud_count}")
    if nonfraud_count > 0:
        log_step("CLASS_BALANCE", f"Imbalance ratio: {(nonfraud_count/fraud_count):.2f}:1 (non-fraud:fraud)")
    
    if fraud_count == 0:
        log_step("CLASS_BALANCE", "❌ ERROR: No fraud samples found!")
        return None
    
    # Undersample non-fraud to match fraud count (1:1 ratio like Kaggle)
    fraction = min(1.0, fraud_count / nonfraud_count) if nonfraud_count > 0 else 1.0
    log_step("CLASS_BALANCE", f"Undersampling non-fraud with fraction={fraction:.4f}")
    nonfraud_sampled = nonfraud_df.sample(withReplacement=False, fraction=fraction, seed=42)
    
    # Combine and shuffle
    balanced_df = fraud_df.union(nonfraud_sampled).orderBy(lit(1))
    
    final_fraud = balanced_df.filter(col(label_col) == 1).count()
    final_nonfraud = balanced_df.filter(col(label_col) == 0).count()
    
    log_step("CLASS_BALANCE", f"Balanced distribution: Fraud={final_fraud}, Non-Fraud={final_nonfraud}")
    log_step("CLASS_BALANCE", "✅ Class balancing complete")
    
    return balanced_df

def train_random_forest(X_train, X_test, y_train, y_test, feature_names):
    """Train Random Forest model - GIỐNG ml_training_job.py"""
    log_step("RF_TRAIN", "🌲 Training Random Forest Classifier...")
    
    run_name = f"RandomForest_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    with mlflow.start_run(run_name=run_name):
        # Log parameters - GIỐNG ml_training_job.py (200 trees, depth 30)
        n_estimators = 200
        max_depth = 30
        mlflow.log_param("model_type", "RandomForest")
        mlflow.log_param("n_estimators", n_estimators)
        mlflow.log_param("max_depth", max_depth)
        mlflow.log_param("min_instances_per_node", 1)
        mlflow.log_param("n_features", len(feature_names))
        mlflow.log_param("framework", "sklearn")
        mlflow.log_param("train_samples", len(X_train))
        mlflow.log_param("test_samples", len(X_test))
        
        # Train model
        log_step("RF_TRAIN", "Training in progress...")
        start_time = datetime.now()
        model = RandomForestClassifier(
            n_estimators=n_estimators,
            max_depth=max_depth,
            min_samples_split=2,  # sklearn minimum is 2
            random_state=42,
            n_jobs=-1
        )
        model.fit(X_train, y_train)
        training_duration = (datetime.now() - start_time).total_seconds()
        
        log_step("RF_TRAIN", f"✅ Training completed in {training_duration:.2f} seconds")
        
        # Predictions
        y_pred = model.predict(X_test)
        y_pred_proba = model.predict_proba(X_test)[:, 1]
        
        # Metrics
        accuracy = accuracy_score(y_test, y_pred)
        precision = precision_score(y_test, y_pred, zero_division=0)
        recall = recall_score(y_test, y_pred, zero_division=0)
        f1 = f1_score(y_test, y_pred, zero_division=0)
        auc = roc_auc_score(y_test, y_pred_proba)
        
        # Confusion matrix
        tn, fp, fn, tp = confusion_matrix(y_test, y_pred).ravel()
        specificity = tn / (tn + fp) if (tn + fp) > 0 else 0.0
        
        mlflow.log_metric("accuracy", accuracy)
        mlflow.log_metric("precision", precision)
        mlflow.log_metric("recall", recall)
        mlflow.log_metric("specificity", specificity)
        mlflow.log_metric("f1_score", f1)
        mlflow.log_metric("auc", auc)
        mlflow.log_metric("training_duration_seconds", training_duration)
        mlflow.log_metric("true_positives", int(tp))
        mlflow.log_metric("true_negatives", int(tn))
        mlflow.log_metric("false_positives", int(fp))
        mlflow.log_metric("false_negatives", int(fn))
        
        log_step("RF_METRICS", "=" * 60)
        log_step("RF_METRICS", f"📈 Model Performance: RandomForest")
        log_step("RF_METRICS", "=" * 60)
        log_step("RF_METRICS", f"Accuracy:     {accuracy:.4f}")
        log_step("RF_METRICS", f"Precision:    {precision:.4f}")
        log_step("RF_METRICS", f"Recall:       {recall:.4f}")
        log_step("RF_METRICS", f"Specificity:  {specificity:.4f}")
        log_step("RF_METRICS", f"F1-Score:     {f1:.4f}")
        log_step("RF_METRICS", f"AUC:          {auc:.4f}")
        log_step("RF_METRICS", "=" * 60)
        log_step("RF_METRICS", "Confusion Matrix:")
        log_step("RF_METRICS", f"  True Positives:  {tp} (Correctly detected fraud)")
        log_step("RF_METRICS", f"  True Negatives:  {tn} (Correctly detected normal)")
        log_step("RF_METRICS", f"  False Positives: {fp} (Normal flagged as fraud)")
        log_step("RF_METRICS", f"  False Negatives: {fn} (Fraud missed)")
        log_step("RF_METRICS", "=" * 60)
        
        # Log model
        mlflow.sklearn.log_model(model, "model", registered_model_name="sklearn_fraud_randomforest")
        log_step("RF_SAVE", "✅ Model saved to MLflow")
        
        # Auto-promote if metrics good - GIỐNG ml_training_job.py
        if accuracy >= 0.90 and f1 >= 0.70 and auc >= 0.90:
            try:
                client = MlflowClient()
                run_id = mlflow.active_run().info.run_id
                model_name = "sklearn_fraud_randomforest"
                
                # Wait for registration
                import time
                time.sleep(2)
                
                # Get latest version
                versions = client.search_model_versions(f"name='{model_name}'")
                if versions:
                    latest_version = max(versions, key=lambda x: int(x.version))
                    version_number = latest_version.version
                    
                    # Promote to Production
                    client.transition_model_version_stage(
                        name=model_name,
                        version=version_number,
                        stage="Production",
                        archive_existing_versions=True
                    )
                    
                    log_step("RF_PROMOTE", f"🎉 Model v{version_number} AUTO-PROMOTED to Production!")
                    log_step("RF_PROMOTE", f"Reason: Accuracy={accuracy:.4f}, F1={f1:.4f}, AUC={auc:.4f}")
                else:
                    log_step("RF_PROMOTE", "⚠️ No model versions found for auto-promotion")
            except Exception as e:
                log_step("RF_PROMOTE", f"⚠️ Auto-promotion failed: {str(e)}")
        else:
            log_step("RF_PROMOTE", f"📉 Model metrics below threshold for auto-promotion:")
            log_step("RF_PROMOTE", f"   Current: Accuracy={accuracy:.4f}, F1={f1:.4f}, AUC={auc:.4f}")
            log_step("RF_PROMOTE", f"   Required: Accuracy>=0.90, F1>=0.70, AUC>=0.90")

def train_logistic_regression(X_train, X_test, y_train, y_test, feature_names):
    """Train Logistic Regression model - GIỐNG ml_training_job.py"""
    log_step("LR_TRAIN", "📈 Training Logistic Regression...")
    
    run_name = f"LogisticRegression_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    with mlflow.start_run(run_name=run_name):
        # Log parameters - GIỐNG ml_training_job.py (max_iter=1000)
        max_iter = 1000
        mlflow.log_param("model_type", "LogisticRegression")
        mlflow.log_param("max_iter", max_iter)
        mlflow.log_param("n_features", len(feature_names))
        mlflow.log_param("framework", "sklearn")
        mlflow.log_param("train_samples", len(X_train))
        mlflow.log_param("test_samples", len(X_test))
        
        # Train model
        log_step("LR_TRAIN", "Training in progress...")
        start_time = datetime.now()
        model = LogisticRegression(
            max_iter=max_iter,
            random_state=42,
            n_jobs=-1
        )
        model.fit(X_train, y_train)
        training_duration = (datetime.now() - start_time).total_seconds()
        
        log_step("LR_TRAIN", f"✅ Training completed in {training_duration:.2f} seconds")
        
        # Predictions
        y_pred = model.predict(X_test)
        y_pred_proba = model.predict_proba(X_test)[:, 1]
        
        # Metrics
        accuracy = accuracy_score(y_test, y_pred)
        precision = precision_score(y_test, y_pred, zero_division=0)
        recall = recall_score(y_test, y_pred, zero_division=0)
        f1 = f1_score(y_test, y_pred, zero_division=0)
        auc = roc_auc_score(y_test, y_pred_proba)
        
        # Confusion matrix
        tn, fp, fn, tp = confusion_matrix(y_test, y_pred).ravel()
        specificity = tn / (tn + fp) if (tn + fp) > 0 else 0.0
        
        mlflow.log_metric("accuracy", accuracy)
        mlflow.log_metric("precision", precision)
        mlflow.log_metric("recall", recall)
        mlflow.log_metric("specificity", specificity)
        mlflow.log_metric("f1_score", f1)
        mlflow.log_metric("auc", auc)
        mlflow.log_metric("training_duration_seconds", training_duration)
        mlflow.log_metric("true_positives", int(tp))
        mlflow.log_metric("true_negatives", int(tn))
        mlflow.log_metric("false_positives", int(fp))
        mlflow.log_metric("false_negatives", int(fn))
        
        log_step("LR_METRICS", "=" * 60)
        log_step("LR_METRICS", f"📈 Model Performance: LogisticRegression")
        log_step("LR_METRICS", "=" * 60)
        log_step("LR_METRICS", f"Accuracy:     {accuracy:.4f}")
        log_step("LR_METRICS", f"Precision:    {precision:.4f}")
        log_step("LR_METRICS", f"Recall:       {recall:.4f}")
        log_step("LR_METRICS", f"Specificity:  {specificity:.4f}")
        log_step("LR_METRICS", f"F1-Score:     {f1:.4f}")
        log_step("LR_METRICS", f"AUC:          {auc:.4f}")
        log_step("LR_METRICS", "=" * 60)
        log_step("LR_METRICS", "Confusion Matrix:")
        log_step("LR_METRICS", f"  True Positives:  {tp} (Correctly detected fraud)")
        log_step("LR_METRICS", f"  True Negatives:  {tn} (Correctly detected normal)")
        log_step("LR_METRICS", f"  False Positives: {fp} (Normal flagged as fraud)")
        log_step("LR_METRICS", f"  False Negatives: {fn} (Fraud missed)")
        log_step("LR_METRICS", "=" * 60)
        
        # Log model
        mlflow.sklearn.log_model(model, "model", registered_model_name="sklearn_fraud_logistic")
        log_step("LR_SAVE", "✅ Model saved to MLflow")
        
        # Auto-promote if metrics good - GIỐNG ml_training_job.py
        if accuracy >= 0.90 and f1 >= 0.70 and auc >= 0.90:
            try:
                client = MlflowClient()
                run_id = mlflow.active_run().info.run_id
                model_name = "sklearn_fraud_logistic"
                
                # Wait for registration
                import time
                time.sleep(2)
                
                # Get latest version
                versions = client.search_model_versions(f"name='{model_name}'")
                if versions:
                    latest_version = max(versions, key=lambda x: int(x.version))
                    version_number = latest_version.version
                    
                    # Promote to Production
                    client.transition_model_version_stage(
                        name=model_name,
                        version=version_number,
                        stage="Production",
                        archive_existing_versions=True
                    )
                    
                    log_step("LR_PROMOTE", f"🎉 Model v{version_number} AUTO-PROMOTED to Production!")
                    log_step("LR_PROMOTE", f"Reason: Accuracy={accuracy:.4f}, F1={f1:.4f}, AUC={auc:.4f}")
                else:
                    log_step("LR_PROMOTE", "⚠️ No model versions found for auto-promotion")
            except Exception as e:
                log_step("LR_PROMOTE", f"⚠️ Auto-promotion failed: {str(e)}")
        else:
            log_step("LR_PROMOTE", f"📉 Model metrics below threshold for auto-promotion:")
            log_step("LR_PROMOTE", f"   Current: Accuracy={accuracy:.4f}, F1={f1:.4f}, AUC={auc:.4f}")
            log_step("LR_PROMOTE", f"   Required: Accuracy>=0.90, F1>=0.70, AUC>=0.90")

def main():
    try:
        log_step("START", "=" * 60)
        log_step("START", "🚀 Starting Sklearn Fraud Detection Model Training")
        log_step("START", "Models: RandomForest, LogisticRegression")
        log_step("START", "=" * 60)
        
        # Create Spark session
        log_step("SPARK", "🔧 Creating Spark session...")
        spark = create_spark_session()
        spark.sparkContext.setLogLevel("WARN")
        log_step("SPARK", "✅ Spark session created")
        
        # Load data from Silver layer
        log_step("DATA_LOAD", "📥 Loading data from Silver layer...")
        silver_path = "s3a://lakehouse/silver/transactions"
        df = spark.read.format("delta").load(silver_path)
        
        initial_count = df.count()
        log_step("DATA_LOAD", f"✅ Loaded {initial_count} records from Silver layer")
        
        # Filter data - GIỐNG ml_training_job.py (chỉ lọc amt > 0)
        log_step("DATA_FILTER", "💰 Using transactions with amt > 0...")
        df = df.filter(col("amt") > 0)
        filtered_count = df.count()
        log_step("DATA_FILTER", f"After removing zero-amount: {filtered_count} records (removed {initial_count - filtered_count})")
        
        # Prepare features - GIỐNG ml_training_job.py
        df, feature_cols = prepare_features(df)
        
        # Handle class imbalance - GIỐNG ml_training_job.py
        df = handle_class_imbalance(df, "is_fraud")
        
        if df is None:
            log_step("ERROR", "❌ Failed to balance dataset")
            return
        
        # Convert to pandas
        log_step("DATA_PREP", "Converting to pandas DataFrame...")
        pdf = df.select(feature_cols + ['is_fraud']).toPandas()
        
        X = pdf[feature_cols].values
        y = pdf['is_fraud'].values
        
        log_step("DATA_PREP", f"✅ Dataset: {X.shape[0]} samples, {X.shape[1]} features")
        log_step("DATA_PREP", f"Fraud ratio: {(y.sum() / len(y) * 100):.2f}%")
        
        # Scale features
        log_step("SCALING", "⚖️ Scaling features (MinMax 0-1)...")
        scaler = MinMaxScaler()
        X_scaled = scaler.fit_transform(X)
        
        # Train/test split - GIỐNG ml_training_job.py (80/20, stratified)
        from sklearn.model_selection import train_test_split
        log_step("SPLIT", "✂️ Splitting data (80/20)...")
        X_train, X_test, y_train, y_test = train_test_split(
            X_scaled, y, test_size=0.2, random_state=42, stratify=y
        )
        log_step("SPLIT", f"Train set: {X_train.shape[0]} samples")
        log_step("SPLIT", f"Test set: {X_test.shape[0]} samples")
        log_step("SPLIT", "✅ Data split complete")
        
        # Train RandomForest
        log_step("PROGRESS", "")
        log_step("PROGRESS", "=" * 60)
        log_step("PROGRESS", "Training Model 1/2: RandomForest")
        log_step("PROGRESS", "=" * 60)
        train_random_forest(X_train, X_test, y_train, y_test, feature_cols)
        
        # Train Logistic Regression
        log_step("PROGRESS", "")
        log_step("PROGRESS", "=" * 60)
        log_step("PROGRESS", "Training Model 2/2: LogisticRegression")
        log_step("PROGRESS", "=" * 60)
        train_logistic_regression(X_train, X_test, y_train, y_test, feature_cols)
        
        log_step("COMPLETE", "")
        log_step("COMPLETE", "=" * 60)
        log_step("COMPLETE", "🎉 Sklearn Model Training Pipeline Completed!")
        log_step("COMPLETE", "=" * 60)
        log_step("COMPLETE", "🔍 Check MLflow UI: http://localhost:5000")
        log_step("COMPLETE", "📦 Models saved: sklearn_fraud_randomforest, sklearn_fraud_logistic")
        
    except Exception as e:
        log_step("ERROR", f"❌ Training failed: {e}")
        import traceback
        log_step("ERROR", traceback.format_exc())
        raise
    finally:
        spark.stop()
        log_step("CLEANUP", "✅ Spark session stopped")

if __name__ == "__main__":
    main()
