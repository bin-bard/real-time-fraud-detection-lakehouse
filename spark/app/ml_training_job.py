from pyspark.sql import SparkSession
from pyspark.ml.feature import VectorAssembler, StandardScaler
from pyspark.ml.classification import RandomForestClassifier, LogisticRegression
from pyspark.ml.evaluation import BinaryClassificationEvaluator, MulticlassClassificationEvaluator
from pyspark.ml import Pipeline
from pyspark.sql.functions import col
import mlflow
import mlflow.spark
import logging
import os

# MLflow configuration - temporarily disabled for testing
# mlflow.set_tracking_uri("http://mlflow:5000")
# mlflow.set_experiment("fraud_detection")
print("⚠️ MLflow tracking is temporarily disabled for testing")

# Cấu hình logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_spark_session():
    """Khởi tạo Spark Session với Delta Lake và MLflow"""
    return SparkSession.builder \
        .appName("FraudDetectionTraining") \
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
        .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog") \
        .config("spark.hadoop.fs.s3a.endpoint", "http://minio:9000") \
        .config("spark.hadoop.fs.s3a.access.key", "minio") \
        .config("spark.hadoop.fs.s3a.secret.key", "minio123") \
        .config("spark.hadoop.fs.s3a.path.style.access", "true") \
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem") \
        .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false") \
        .getOrCreate()

def prepare_features(df):
    """
    Chuẩn bị features cho machine learning
    """
    logger.info("Preparing features for ML...")
    
    # Chọn các features để training (loại bỏ các columns không cần thiết)
    feature_cols = [
        "Time", "Amount", "log_amount", "is_zero_amount", "is_high_amount",
        "hour_of_day", "day_of_week", "amount_v1_ratio", "v1_v2_interaction"
    ] + [f"V{i}" for i in range(1, 29)]
    
    # Vector assembler
    assembler = VectorAssembler(
        inputCols=feature_cols,
        outputCol="features_raw"
    )
    
    # Standard scaler  
    scaler = StandardScaler(
        inputCol="features_raw",
        outputCol="features",
        withStd=True,
        withMean=True
    )
    
    return assembler, scaler

def train_model(algorithm="random_forest"):
    """
    Huấn luyện mô hình fraud detection
    """
    spark = create_spark_session()
    spark.sparkContext.setLogLevel("WARN")
    
    logger.info(f"🤖 Starting model training with {algorithm}...")
    
    silver_path = "s3a://lakehouse/silver/transactions"
    
    try:
        # Đọc dữ liệu từ Silver layer
        logger.info("Loading data from Silver layer...")
        df = spark.read.format("delta").load(silver_path)
        
        # Đổi tên target column
        df = df.withColumnRenamed("Class", "label")
        
        logger.info(f"Total samples: {df.count()}")
        
        # Split data
        train_df, test_df = df.randomSplit([0.8, 0.2], seed=42)
        
        logger.info(f"Training samples: {train_df.count()}")
        logger.info(f"Test samples: {test_df.count()}")
        
        # Prepare features
        assembler, scaler = prepare_features(df)
        
        # Choose algorithm
        if algorithm == "random_forest":
            classifier = RandomForestClassifier(
                featuresCol="features",
                labelCol="label", 
                numTrees=100,
                maxDepth=10,
                seed=42
            )
        else:  # logistic_regression
            classifier = LogisticRegression(
                featuresCol="features",
                labelCol="label",
                maxIter=100,
                regParam=0.01
            )
        
        # Create pipeline
        pipeline = Pipeline(stages=[assembler, scaler, classifier])
        
        # Start MLflow run - temporarily disabled
        # with mlflow.start_run(run_name=f"fraud_detection_{algorithm}"):
        
        # Log parameters - temporarily disabled  
        # if algorithm == "random_forest":
        #     mlflow.log_param("num_trees", 100)
        #     mlflow.log_param("max_depth", 10)
        # else:
        #     mlflow.log_param("max_iter", 100)
        #     mlflow.log_param("reg_param", 0.01)
        #     
        # mlflow.log_param("algorithm", algorithm)
        # mlflow.log_param("train_samples", train_df.count())
        # mlflow.log_param("test_samples", test_df.count())
        
        # Train model
        logger.info("Training model...")
        model = pipeline.fit(train_df)
        
        # Make predictions
        logger.info("Making predictions...")
        predictions = model.transform(test_df)
        
        # Evaluate model
        logger.info("Evaluating model...")
        
        # Binary classification metrics
        binary_evaluator = BinaryClassificationEvaluator(
            labelCol="label",
            rawPredictionCol="rawPrediction",
            metricName="areaUnderROC"
        )
        auc = binary_evaluator.evaluate(predictions)
        
        # Precision and Recall
        multiclass_evaluator = MulticlassClassificationEvaluator(
            labelCol="label",
            predictionCol="prediction"
        )
        
        accuracy = multiclass_evaluator.evaluate(predictions, {multiclass_evaluator.metricName: "accuracy"})
        precision = multiclass_evaluator.evaluate(predictions, {multiclass_evaluator.metricName: "weightedPrecision"})
        recall = multiclass_evaluator.evaluate(predictions, {multiclass_evaluator.metricName: "weightedRecall"})
        f1 = multiclass_evaluator.evaluate(predictions, {multiclass_evaluator.metricName: "f1"})
        
        # Log metrics - temporarily disabled
        # mlflow.log_metric("auc", auc)
        # mlflow.log_metric("accuracy", accuracy)
        # mlflow.log_metric("precision", precision)
        # mlflow.log_metric("recall", recall)
        # mlflow.log_metric("f1_score", f1)
        
        # Log model - temporarily disabled
        # mlflow.spark.log_model(
        #     model,
        #     "fraud_detection_model",
        #     registered_model_name=f"fraud_detection_{algorithm}"
        # )
        
        logger.info("📊 Model Performance:")
        logger.info(f"   AUC: {auc:.4f}")
        logger.info(f"   Accuracy: {accuracy:.4f}")
        logger.info(f"   Precision: {precision:.4f}")
        logger.info(f"   Recall: {recall:.4f}")
        logger.info(f"   F1-Score: {f1:.4f}")
        
        # Tính fraud detection specific metrics
        fraud_predictions = predictions.filter(col("label") == 1)
        total_fraud = fraud_predictions.count()
        detected_fraud = fraud_predictions.filter(col("prediction") == 1).count()
        
        if total_fraud > 0:
            fraud_detection_rate = detected_fraud / total_fraud
            # mlflow.log_metric("fraud_detection_rate", fraud_detection_rate) # temporarily disabled
            logger.info(f"   Fraud Detection Rate: {fraud_detection_rate:.4f}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error in model training: {str(e)}")
        return False
    finally:
        spark.stop()

def train_multiple_models():
    """
    Huấn luyện nhiều models để so sánh
    """
    algorithms = ["random_forest", "logistic_regression"]
    
    for algorithm in algorithms:
        logger.info(f"🔄 Training {algorithm} model...")
        success = train_model(algorithm)
        if not success:
            logger.error(f"Failed to train {algorithm}")
            
    logger.info("🎉 All models training completed!")

if __name__ == "__main__":
    train_multiple_models()