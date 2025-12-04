from pyspark.sql import SparkSession
from pyspark.ml.feature import VectorAssembler, MinMaxScaler
from pyspark.ml.classification import RandomForestClassifier, LogisticRegression
from pyspark.ml.evaluation import BinaryClassificationEvaluator, MulticlassClassificationEvaluator
from pyspark.ml import Pipeline
from pyspark.sql.functions import col, when, lit, isnan, isnull
from pyspark.sql.types import DoubleType, IntegerType
import mlflow
import mlflow.spark
from mlflow.tracking import MlflowClient
import logging
import os
import sys
from datetime import datetime

# Configure MLflow S3 artifact storage
os.environ["AWS_ACCESS_KEY_ID"] = "minio"
os.environ["AWS_SECRET_ACCESS_KEY"] = "minio123"
os.environ["MLFLOW_S3_ENDPOINT_URL"] = "http://minio:9000"
os.environ["GIT_PYTHON_REFRESH"] = "quiet"

# MLflow configuration
mlflow.set_tracking_uri("http://mlflow:5000")
mlflow.set_experiment("fraud_detection_production")

# Logging configuration - with stdout flush for Airflow visibility
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

def log_step(step_name, message):
    """Log with step prefix for Airflow visibility"""
    full_message = f"[STEP: {step_name}] {message}"
    logger.info(full_message)
    sys.stdout.flush()  # Force flush to appear in Airflow logs immediately

def create_spark_session():
    """Initialize Spark Session with Delta Lake"""
    return SparkSession.builder \
        .appName("FraudDetectionMLTraining") \
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
        .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog") \
        .config("spark.hadoop.fs.s3a.endpoint", "http://minio:9000") \
        .config("spark.hadoop.fs.s3a.access.key", "minio") \
        .config("spark.hadoop.fs.s3a.secret.key", "minio123") \
        .config("spark.hadoop.fs.s3a.path.style.access", "true") \
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem") \
        .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false") \
        .config("spark.sql.adaptive.enabled", "true") \
        .config("spark.sql.parquet.datetimeRebaseModeInWrite", "LEGACY") \
        .config("spark.sql.parquet.int96RebaseModeInWrite", "LEGACY") \
        .getOrCreate()

def prepare_features(df):
    """
    Feature engineering - MUST match exactly with Silver layer features
    """
    log_step("FEATURE_PREP", "🔧 Preparing features for ML training...")
    
    # IMPORTANT: These features MUST exist in Silver layer
    # Check silver_job.py feature_engineering() function
    feature_cols = [
        # Transaction amount features (from silver_job.py)
        "amt", "log_amount", "is_zero_amount", "is_high_amount", "amount_bin",
        
        # Geographic features (from silver_job.py)
        "distance_km", "is_distant_transaction",
        "lat", "long", "merch_lat", "merch_long", "city_pop",
        
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
    
    log_step("FEATURE_PREP", f"📊 Using {len(available_features)}/{len(feature_cols)} features")
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
    
    # Vector assembler
    log_step("FEATURE_PREP", "Creating feature vector...")
    assembler = VectorAssembler(
        inputCols=available_features,
        outputCol="features_raw",
        handleInvalid="skip"
    )
    
    # MinMax Scaler (0-1 normalization like Kaggle)
    log_step("FEATURE_PREP", "Creating MinMax scaler (0-1 normalization)...")
    scaler = MinMaxScaler(
        inputCol="features_raw",
        outputCol="features"
    )
    
    log_step("FEATURE_PREP", "✅ Feature preparation complete")
    return assembler, scaler, available_features

def handle_class_imbalance(df, label_col="label"):
    """
    Handle imbalanced data - Kaggle approach
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

def train_model(spark, model_name="RandomForest"):
    """
    Train fraud detection model following Kaggle best practices
    Models: RandomForest, LogisticRegression
    """
    log_step("INIT", f"🚀 Starting model training: {model_name}")
    log_step("INIT", f"⏰ Training started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    silver_path = "s3a://lakehouse/silver/transactions"
    
    try:
        # Load data from Silver layer
        log_step("DATA_LOAD", "📥 Loading data from Silver layer...")
        log_step("DATA_LOAD", f"Reading from: {silver_path}")
        df = spark.read.format("delta").load(silver_path)
        
        initial_count = df.count()
        log_step("DATA_LOAD", f"✅ Loaded {initial_count} records from Silver layer")
        
        # Show schema to verify features exist
        log_step("DATA_LOAD", "Verifying Silver layer schema...")
        available_cols = df.columns
        log_step("DATA_LOAD", f"Available columns: {len(available_cols)} columns")
        
        # Note: Removed amt filtering - using all valid transactions
        # Previous filter (amt >= 5 AND <= 1250) was too restrictive
        log_step("DATA_FILTER", "📊 Using all transactions with amt > 0...")
        df = df.filter(col("amt") > 0)
        filtered_count = df.count()
        log_step("DATA_FILTER", f"After removing zero-amount: {filtered_count} records (removed {initial_count - filtered_count})")
        
        # Prepare label
        log_step("DATA_PREP", "Preparing label column...")
        df = df.withColumn("label", col("is_fraud").cast(IntegerType()))
        df = df.filter(col("label").isNotNull())
        log_step("DATA_PREP", "✅ Label column prepared (0=Normal, 1=Fraud)")
        
        # Prepare features
        assembler, scaler, feature_cols = prepare_features(df)
        
        # Handle class imbalance
        df = handle_class_imbalance(df, "label")
        
        if df is None:
            log_step("ERROR", "❌ Failed to balance dataset")
            return False
        
        # Train-test split (80-20 like Kaggle)
        log_step("DATA_SPLIT", "Splitting data into train/test (80/20)...")
        train_df, test_df = df.randomSplit([0.8, 0.2], seed=42)
        
        train_count = train_df.count()
        test_count = test_df.count()
        log_step("DATA_SPLIT", f"Train set: {train_count} samples")
        log_step("DATA_SPLIT", f"Test set: {test_count} samples")
        log_step("DATA_SPLIT", "✅ Data split complete")
        
        # Cache for performance
        log_step("OPTIMIZATION", "Caching datasets for better performance...")
        train_df = train_df.cache()
        test_df = test_df.cache()
        log_step("OPTIMIZATION", "✅ Datasets cached")
        
        # Select classifier - Only RandomForest and LogisticRegression
        log_step("MODEL_CONFIG", f"Configuring {model_name} classifier...")
        
        if model_name == "RandomForest":
            log_step("MODEL_CONFIG", "Parameters: numTrees=200, maxDepth=30, minInstancesPerNode=1")
            classifier = RandomForestClassifier(
                featuresCol="features",
                labelCol="label",
                numTrees=200,
                maxDepth=30,
                minInstancesPerNode=1,
                seed=42
            )
        elif model_name == "LogisticRegression":
            log_step("MODEL_CONFIG", "Parameters: maxIter=1000, regParam=0.0, elasticNetParam=0.0")
            classifier = LogisticRegression(
                featuresCol="features",
                labelCol="label",
                maxIter=1000,
                regParam=0.0,
                elasticNetParam=0.0,
                standardization=False
            )
        else:
            log_step("ERROR", f"❌ Unknown model: {model_name}")
            return False
        
        log_step("MODEL_CONFIG", "✅ Classifier configured")
        
        # Create pipeline
        log_step("PIPELINE", "Creating ML pipeline (assembler → scaler → classifier)...")
        pipeline = Pipeline(stages=[assembler, scaler, classifier])
        log_step("PIPELINE", "✅ Pipeline created")
        
        # Start MLflow run
        run_name = f"{model_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        log_step("MLFLOW", f"Starting MLflow run: {run_name}")
        
        with mlflow.start_run(run_name=run_name):
            
            # Log parameters
            log_step("MLFLOW", "Logging parameters to MLflow...")
            mlflow.log_param("model", model_name)
            mlflow.log_param("train_samples", train_count)
            mlflow.log_param("test_samples", test_count)
            mlflow.log_param("num_features", len(feature_cols))
            mlflow.log_param("features", ",".join(feature_cols[:10]) + ("..." if len(feature_cols) > 10 else ""))
            
            if model_name == "RandomForest":
                mlflow.log_param("num_trees", 200)
                mlflow.log_param("max_depth", 30)
            elif model_name == "LogisticRegression":
                mlflow.log_param("max_iter", 1000)
            
            log_step("MLFLOW", "✅ Parameters logged")
            
            # Train model
            log_step("TRAINING", f"🏋️ Training {model_name} model...")
            log_step("TRAINING", "This may take several minutes...")
            start_time = datetime.now()
            model = pipeline.fit(train_df)
            training_duration = (datetime.now() - start_time).total_seconds()
            log_step("TRAINING", f"✅ Training completed in {training_duration:.2f} seconds ({training_duration/60:.2f} minutes)")
            
            # Predictions
            log_step("PREDICTION", "🔮 Making predictions on test set...")
            predictions = model.transform(test_df)
            log_step("PREDICTION", "✅ Predictions complete")
            
            # Evaluation
            log_step("EVALUATION", "📈 Evaluating model performance...")
            
            # Binary metrics
            binary_evaluator = BinaryClassificationEvaluator(labelCol="label", rawPredictionCol="rawPrediction")
            auc = binary_evaluator.evaluate(predictions, {binary_evaluator.metricName: "areaUnderROC"})
            
            # Multiclass metrics
            multiclass_evaluator = MulticlassClassificationEvaluator(labelCol="label", predictionCol="prediction")
            accuracy = multiclass_evaluator.evaluate(predictions, {multiclass_evaluator.metricName: "accuracy"})
            precision = multiclass_evaluator.evaluate(predictions, {multiclass_evaluator.metricName: "weightedPrecision"})
            recall = multiclass_evaluator.evaluate(predictions, {multiclass_evaluator.metricName: "weightedRecall"})
            f1 = multiclass_evaluator.evaluate(predictions, {multiclass_evaluator.metricName: "f1"})
            
            # Confusion matrix
            tp = predictions.filter((col("label") == 1) & (col("prediction") == 1)).count()
            tn = predictions.filter((col("label") == 0) & (col("prediction") == 0)).count()
            fp = predictions.filter((col("label") == 0) & (col("prediction") == 1)).count()
            fn = predictions.filter((col("label") == 1) & (col("prediction") == 0)).count()
            specificity = tn / (tn + fp) if (tn + fp) > 0 else 0.0
            
            log_step("EVALUATION", "✅ Evaluation complete")
            
            # Log metrics
            log_step("MLFLOW", "Logging metrics to MLflow...")
            mlflow.log_metric("accuracy", accuracy)
            mlflow.log_metric("precision", precision)
            mlflow.log_metric("recall", recall)
            mlflow.log_metric("specificity", specificity)
            mlflow.log_metric("f1_score", f1)
            mlflow.log_metric("auc", auc)
            mlflow.log_metric("training_duration_seconds", training_duration)
            mlflow.log_metric("true_positives", tp)
            mlflow.log_metric("true_negatives", tn)
            mlflow.log_metric("false_positives", fp)
            mlflow.log_metric("false_negatives", fn)
            
            # Log model
            log_step("MLFLOW", "Saving model to MLflow...")
            mlflow.spark.log_model(model, "model", registered_model_name=f"fraud_detection_{model_name.lower()}")
            log_step("MLFLOW", f"✅ Model registered: fraud_detection_{model_name.lower()}")
            
            # Get current run ID and model version
            run_id = mlflow.active_run().info.run_id
            
            # AUTO-PROMOTE to Production if metrics are good
            log_step("MLFLOW", "Checking if model should be promoted to Production...")
            if accuracy >= 0.90 and f1 >= 0.85 and auc >= 0.90:
                try:
                    client = MlflowClient()
                    model_name_full = f"fraud_detection_{model_name.lower()}"
                    
                    # Wait a bit for model registration to complete
                    import time
                    time.sleep(2)
                    
                    # Get the latest version
                    versions = client.search_model_versions(f"name='{model_name_full}'")
                    if versions:
                        latest_version = max(versions, key=lambda x: int(x.version))
                        version_number = latest_version.version
                        
                        # Transition to Production
                        client.transition_model_version_stage(
                            name=model_name_full,
                            version=version_number,
                            stage="Production",
                            archive_existing_versions=True  # Auto-archive old Production models
                        )
                        
                        log_step("MLFLOW", f"🎉 Model v{version_number} AUTO-PROMOTED to Production!")
                        log_step("MLFLOW", f"Reason: Accuracy={accuracy:.4f}, F1={f1:.4f}, AUC={auc:.4f}")
                    else:
                        log_step("MLFLOW", "⚠️ No model versions found for auto-promotion")
                        
                except Exception as e:
                    log_step("MLFLOW", f"⚠️ Auto-promotion failed: {str(e)}")
                    log_step("MLFLOW", "You can manually promote in MLflow UI: http://localhost:5000")
            else:
                log_step("MLFLOW", f"📊 Model metrics below threshold for auto-promotion:")
                log_step("MLFLOW", f"   Current: Accuracy={accuracy:.4f}, F1={f1:.4f}, AUC={auc:.4f}")
                log_step("MLFLOW", f"   Required: Accuracy>=0.90, F1>=0.85, AUC>=0.90")
                log_step("MLFLOW", "   Manual promotion available in MLflow UI: http://localhost:5000")
            
            # Print results
            log_step("RESULTS", "=" * 60)
            log_step("RESULTS", f"📊 Model Performance: {model_name}")
            log_step("RESULTS", "=" * 60)
            log_step("RESULTS", f"Accuracy:     {accuracy:.4f}")
            log_step("RESULTS", f"Precision:    {precision:.4f}")
            log_step("RESULTS", f"Recall:       {recall:.4f}")
            log_step("RESULTS", f"Specificity:  {specificity:.4f}")
            log_step("RESULTS", f"F1-Score:     {f1:.4f}")
            log_step("RESULTS", f"AUC:          {auc:.4f}")
            log_step("RESULTS", "=" * 60)
            log_step("RESULTS", "Confusion Matrix:")
            log_step("RESULTS", f"  True Positives:  {tp} (Correctly detected fraud)")
            log_step("RESULTS", f"  True Negatives:  {tn} (Correctly detected normal)")
            log_step("RESULTS", f"  False Positives: {fp} (Normal flagged as fraud)")
            log_step("RESULTS", f"  False Negatives: {fn} (Fraud missed)")
            log_step("RESULTS", "=" * 60)
        
        log_step("SUCCESS", f"✅ {model_name} training completed successfully!")
        return True
        
    except Exception as e:
        log_step("ERROR", f"❌ Error in model training: {str(e)}")
        import traceback
        log_step("ERROR", traceback.format_exc())
        return False

def train_all_models():
    """Train RandomForest and LogisticRegression models"""
    log_step("START", "=" * 60)
    log_step("START", "🎯 Starting Fraud Detection Model Training")
    log_step("START", "Models: RandomForest, LogisticRegression")
    log_step("START", "=" * 60)
    
    log_step("SPARK", "Initializing Spark session...")
    spark = create_spark_session()
    spark.sparkContext.setLogLevel("WARN")
    log_step("SPARK", "✅ Spark session created")
    
    models = ["RandomForest", "LogisticRegression"]
    results = []
    
    try:
        for idx, model_name in enumerate(models, 1):
            log_step("PROGRESS", "")
            log_step("PROGRESS", "=" * 60)
            log_step("PROGRESS", f"Training Model {idx}/{len(models)}: {model_name}")
            log_step("PROGRESS", "=" * 60)
            
            success = train_model(spark, model_name)
            results.append({"model": model_name, "success": success})
            
            if success:
                log_step("PROGRESS", f"✅ {model_name} completed")
            else:
                log_step("PROGRESS", f"❌ {model_name} failed")
            
    finally:
        log_step("CLEANUP", "Stopping Spark session...")
        spark.stop()
        log_step("CLEANUP", "✅ Spark session stopped")
        
        log_step("SUMMARY", "")
        log_step("SUMMARY", "=" * 60)
        log_step("SUMMARY", "🎉 Model Training Pipeline Completed!")
        log_step("SUMMARY", "=" * 60)
        log_step("SUMMARY", "Results Summary:")
        for result in results:
            status = "✅ Success" if result["success"] else "❌ Failed"
            log_step("SUMMARY", f"  {result['model']}: {status}")
        log_step("SUMMARY", "=" * 60)
        log_step("SUMMARY", "📊 Check MLflow UI: http://localhost:5000")

if __name__ == "__main__":
    train_all_models()
