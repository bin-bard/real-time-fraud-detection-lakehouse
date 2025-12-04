from pyspark.sql import SparkSession
from pyspark.ml.feature import VectorAssembler, MinMaxScaler
from pyspark.ml.classification import RandomForestClassifier, LogisticRegression, GBTClassifier, DecisionTreeClassifier
from pyspark.ml.evaluation import BinaryClassificationEvaluator, MulticlassClassificationEvaluator
from pyspark.ml import Pipeline
from pyspark.sql.functions import col, when, lit, isnan, isnull, count as spark_count
from pyspark.sql.types import DoubleType, IntegerType
import mlflow
import mlflow.spark
import logging
import os
from datetime import datetime

# Configure MLflow S3 artifact storage
os.environ["AWS_ACCESS_KEY_ID"] = "minio"
os.environ["AWS_SECRET_ACCESS_KEY"] = "minio123"
os.environ["MLFLOW_S3_ENDPOINT_URL"] = "http://minio:9000"
os.environ["GIT_PYTHON_REFRESH"] = "quiet"

# MLflow configuration
mlflow.set_tracking_uri("http://mlflow:5000")
mlflow.set_experiment("fraud_detection_production")

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

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
    Feature engineering based on Kaggle best practices
    """
    logger.info("🔧 Preparing features for ML training...")
    
    # Select features similar to Kaggle notebook
    feature_cols = [
        # Transaction amount features
        "amt", "log_amount", "is_zero_amount", "is_high_amount", "amount_bin",
        
        # Geographic features (similar to lat, long, merch_lat, merch_long in Kaggle)
        "distance_km", "is_distant_transaction",
        "lat", "long", "merch_lat", "merch_long", "city_pop",
        
        # Demographic features (age from dob like Kaggle)
        "age", "gender_encoded",
        
        # Time features (trans_hour, trans_dayofweek in Kaggle)
        "hour", "day_of_week", "is_weekend", "is_late_night",
        "hour_sin", "hour_cos"
    ]
    
    # Check available columns
    available_features = [f for f in feature_cols if f in df.columns]
    logger.info(f"📊 Using {len(available_features)} features: {available_features}")
    
    # Fill missing values with median (Kaggle approach)
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
    assembler = VectorAssembler(
        inputCols=available_features,
        outputCol="features_raw",
        handleInvalid="skip"
    )
    
    # MinMax Scaler (0-1 normalization like Kaggle)
    scaler = MinMaxScaler(
        inputCol="features_raw",
        outputCol="features"
    )
    
    return assembler, scaler, available_features

def handle_class_imbalance(df, label_col="label"):
    """
    Handle imbalanced data - Kaggle approach
    Undersample majority class to balance dataset
    """
    logger.info("⚖️ Handling class imbalance...")
    
    # Count fraud and non-fraud
    fraud_df = df.filter(col(label_col) == 1).cache()
    nonfraud_df = df.filter(col(label_col) == 0)
    
    fraud_count = fraud_df.count()
    nonfraud_count = nonfraud_df.count()
    
    logger.info(f"Original distribution: Fraud={fraud_count}, Non-Fraud={nonfraud_count}")
    
    if fraud_count == 0:
        logger.error("❌ No fraud samples found!")
        return None
    
    # Undersample non-fraud to match fraud count (1:1 ratio like Kaggle)
    fraction = min(1.0, fraud_count / nonfraud_count)
    nonfraud_sampled = nonfraud_df.sample(withReplacement=False, fraction=fraction, seed=42)
    
    # Combine and shuffle
    balanced_df = fraud_df.union(nonfraud_sampled).orderBy(lit(1))
    
    final_fraud = balanced_df.filter(col(label_col) == 1).count()
    final_nonfraud = balanced_df.filter(col(label_col) == 0).count()
    
    logger.info(f"Balanced distribution: Fraud={final_fraud}, Non-Fraud={final_nonfraud}")
    
    return balanced_df

def train_model(spark, model_name="GradientBoosting"):
    """
    Train fraud detection model following Kaggle best practices
    Models: RandomForest, DecisionTree, LogisticRegression, GradientBoosting
    """
    logger.info(f"🚀 Starting model training: {model_name}")
    logger.info(f"⏰ Training started at: {datetime.now()}")
    
    silver_path = "s3a://lakehouse/silver/transactions"
    
    try:
        # Load data from Silver layer
        logger.info("📥 Loading data from Silver layer...")
        df = spark.read.format("delta").load(silver_path)
        
        initial_count = df.count()
        logger.info(f"Initial dataset: {initial_count} records")
        
        # Filter extreme transaction amounts (similar to Kaggle: amt >= 5 and <= 1250)
        logger.info("🔍 Filtering extreme transaction amounts...")
        df = df.filter((col("amt") >= 5) & (col("amt") <= 1250))
        filtered_count = df.count()
        logger.info(f"After filtering: {filtered_count} records (removed {initial_count - filtered_count})")
        
        # Prepare label
        df = df.withColumn("label", col("is_fraud").cast(IntegerType()))
        df = df.filter(col("label").isNotNull())
        
        # Prepare features
        assembler, scaler, feature_cols = prepare_features(df)
        
        # Handle class imbalance
        df = handle_class_imbalance(df, "label")
        
        if df is None:
            logger.error("❌ Failed to balance dataset")
            return False
        
        # Train-test split (80-20 like Kaggle)
        train_df, test_df = df.randomSplit([0.8, 0.2], seed=42)
        
        train_count = train_df.count()
        test_count = test_df.count()
        logger.info(f"📊 Train/Test split: {train_count}/{test_count}")
        
        # Cache for performance
        train_df = train_df.cache()
        test_df = test_df.cache()
        
        # Select classifier (Kaggle models)
        if model_name == "RandomForest":
            classifier = RandomForestClassifier(
                featuresCol="features",
                labelCol="label",
                numTrees=200,  # Kaggle uses 200
                maxDepth=30,
                minInstancesPerNode=1,
                seed=42
            )
        elif model_name == "DecisionTree":
            classifier = DecisionTreeClassifier(
                featuresCol="features",
                labelCol="label",
                maxDepth=30,
                seed=42
            )
        elif model_name == "LogisticRegression":
            classifier = LogisticRegression(
                featuresCol="features",
                labelCol="label",
                maxIter=1000,  # Kaggle uses 1000
                regParam=0.0,
                elasticNetParam=0.0,
                standardization=False  # Already scaled
            )
        else:  # GradientBoosting
            classifier = GBTClassifier(
                featuresCol="features",
                labelCol="label",
                maxIter=300,  # Kaggle: n_estimators=300
                maxDepth=3,   # Kaggle: max_depth=3
                stepSize=0.05,  # Kaggle: learning_rate=0.05
                seed=42
            )
        
        # Create pipeline
        pipeline = Pipeline(stages=[assembler, scaler, classifier])
        
        # Start MLflow run
        with mlflow.start_run(run_name=f"{model_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"):
            
            # Log parameters
            mlflow.log_param("model", model_name)
            mlflow.log_param("train_samples", train_count)
            mlflow.log_param("test_samples", test_count)
            mlflow.log_param("num_features", len(feature_cols))
            mlflow.log_param("features", feature_cols)
            
            if model_name == "RandomForest":
                mlflow.log_param("num_trees", 200)
                mlflow.log_param("max_depth", 30)
            elif model_name == "GradientBoosting":
                mlflow.log_param("max_iter", 300)
                mlflow.log_param("max_depth", 3)
                mlflow.log_param("step_size", 0.05)
            elif model_name == "LogisticRegression":
                mlflow.log_param("max_iter", 1000)
            
            # Train model
            logger.info(f"🏋️ Training {model_name}...")
            start_time = datetime.now()
            model = pipeline.fit(train_df)
            training_duration = (datetime.now() - start_time).total_seconds()
            logger.info(f"✅ Training completed in {training_duration:.2f} seconds")
            
            # Predictions
            logger.info("🔮 Making predictions...")
            predictions = model.transform(test_df)
            
            # Evaluation
            logger.info("📈 Evaluating model...")
            
            # Binary metrics
            binary_evaluator = BinaryClassificationEvaluator(
                labelCol="label",
                rawPredictionCol="rawPrediction"
            )
            auc = binary_evaluator.evaluate(predictions, {binary_evaluator.metricName: "areaUnderROC"})
            
            # Multiclass metrics
            multiclass_evaluator = MulticlassClassificationEvaluator(labelCol="label", predictionCol="prediction")
            
            accuracy = multiclass_evaluator.evaluate(predictions, {multiclass_evaluator.metricName: "accuracy"})
            precision = multiclass_evaluator.evaluate(predictions, {multiclass_evaluator.metricName: "weightedPrecision"})
            recall = multiclass_evaluator.evaluate(predictions, {multiclass_evaluator.metricName: "weightedRecall"})
            f1 = multiclass_evaluator.evaluate(predictions, {multiclass_evaluator.metricName: "f1"})
            
            # Confusion matrix calculations
            tp = predictions.filter((col("label") == 1) & (col("prediction") == 1)).count()
            tn = predictions.filter((col("label") == 0) & (col("prediction") == 0)).count()
            fp = predictions.filter((col("label") == 0) & (col("prediction") == 1)).count()
            fn = predictions.filter((col("label") == 1) & (col("prediction") == 0)).count()
            
            # Specificity (True Negative Rate)
            specificity = tn / (tn + fp) if (tn + fp) > 0 else 0.0
            
            # Log metrics
            mlflow.log_metric("accuracy", accuracy)
            mlflow.log_metric("precision", precision)
            mlflow.log_metric("recall", recall)
            mlflow.log_metric("specificity", specificity)
            mlflow.log_metric("f1_score", f1)
            mlflow.log_metric("auc", auc)
            mlflow.log_metric("training_duration_seconds", training_duration)
            
            # Log confusion matrix values
            mlflow.log_metric("true_positives", tp)
            mlflow.log_metric("true_negatives", tn)
            mlflow.log_metric("false_positives", fp)
            mlflow.log_metric("false_negatives", fn)
            
            # Log model
            mlflow.spark.log_model(
                model,
                "model",
                registered_model_name=f"fraud_detection_{model_name.lower()}"
            )
            
            # Print results (Kaggle-style)
            logger.info("\n" + "="*60)
            logger.info(f"📊 Model Performance: {model_name}")
            logger.info("="*60)
            logger.info(f"Accuracy:     {accuracy:.4f}")
            logger.info(f"Precision:    {precision:.4f}")
            logger.info(f"Recall:       {recall:.4f}")
            logger.info(f"Specificity:  {specificity:.4f}")
            logger.info(f"F1-Score:     {f1:.4f}")
            logger.info(f"AUC:          {auc:.4f}")
            logger.info("="*60)
            logger.info("\nConfusion Matrix:")
            logger.info(f"True Positives:  {tp}")
            logger.info(f"True Negatives:  {tn}")
            logger.info(f"False Positives: {fp}")
            logger.info(f"False Negatives: {fn}")
            logger.info("="*60 + "\n")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error in model training: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def train_all_models():
    """
    Train all models and compare (like Kaggle notebook)
    """
    logger.info("🎯 Starting comprehensive model training...")
    logger.info("="*60)
    
    spark = create_spark_session()
    spark.sparkContext.setLogLevel("WARN")
    
    # Models to train (same as Kaggle)
    models = ["RandomForest", "DecisionTree", "LogisticRegression", "GradientBoosting"]
    
    results = []
    try:
        for model_name in models:
            logger.info(f"\n{'='*60}")
            logger.info(f"Training: {model_name}")
            logger.info(f"{'='*60}\n")
            
            success = train_model(spark, model_name)
            results.append({"model": model_name, "success": success})
            
            if success:
                logger.info(f"✅ {model_name} training completed successfully")
            else:
                logger.error(f"❌ {model_name} training failed")
            
    finally:
        spark.stop()
        logger.info("\n" + "="*60)
        logger.info("🎉 All model training completed!")
        logger.info("="*60)
        logger.info("\nResults Summary:")
        for result in results:
            status = "✅ Success" if result["success"] else "❌ Failed"
            logger.info(f"  {result['model']}: {status}")
        logger.info("="*60)

if __name__ == "__main__":
    train_all_models()
