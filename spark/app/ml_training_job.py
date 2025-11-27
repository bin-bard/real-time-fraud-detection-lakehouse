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

# Configure MLflow S3 artifact storage
os.environ["AWS_ACCESS_KEY_ID"] = "minio"
os.environ["AWS_SECRET_ACCESS_KEY"] = "minio123"
os.environ["MLFLOW_S3_ENDPOINT_URL"] = "http://minio:9000"

# MLflow configuration
mlflow.set_tracking_uri("http://mlflow:5000")
mlflow.set_experiment("fraud_detection")
print("✅ MLflow tracking enabled - connected to http://mlflow:5000")
print(f"✅ MLflow artifacts will be stored in S3: {os.environ.get('MLFLOW_S3_ENDPOINT_URL')}")

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
    Chuẩn bị features cho machine learning từ Sparkov dataset
    Sử dụng các features đã được engineer trong Silver layer
    """
    logger.info("Preparing features for ML...")
    
    # Chọn các features quan trọng cho fraud detection
    feature_cols = [
        # Transaction features
        "amt", "log_amount", "amount_bin",
        "is_zero_amount", "is_high_amount",
        
        # Geographic features
        "distance_km", "is_distant_transaction",
        
        # Demographic features
        "age", "gender_encoded",
        
        # Time features
        "hour", "day_of_week", "is_weekend", "is_late_night",
        "hour_sin", "hour_cos"
    ]
    
    # Vector assembler
    assembler = VectorAssembler(
        inputCols=feature_cols,
        outputCol="features_raw",
        handleInvalid="skip"  # Skip rows with invalid values
    )
    
    # Standard scaler  
    scaler = StandardScaler(
        inputCol="features_raw",
        outputCol="features",
        withStd=True,
        withMean=True
    )
    
    logger.info(f"Selected {len(feature_cols)} features for training")
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
        
        # Cast is_fraud to integer for ML
        df = df.withColumn("is_fraud", col("is_fraud").cast("integer"))
        
        # Đổi tên target column
        df = df.withColumnRenamed("is_fraud", "label")
        
        logger.info(f"Total samples: {df.count()}")
        
        # Check class distribution
        fraud_count = df.filter(col("label") == 1).count()
        normal_count = df.filter(col("label") == 0).count()
        logger.info(f"Fraud samples: {fraud_count}")
        logger.info(f"Normal samples: {normal_count}")
        logger.info(f"Fraud ratio: {fraud_count/(fraud_count+normal_count)*100:.2f}%")
        
        # Handle class imbalance - undersample normal transactions
        # Keep all fraud transactions, sample normal transactions
        fraud_df = df.filter(col("label") == 1)
        normal_df = df.filter(col("label") == 0)
        
        # Sample normal transactions to balance (e.g., 3:1 ratio)
        sample_ratio = min(1.0, (fraud_count * 3) / normal_count)
        normal_sampled = normal_df.sample(withReplacement=False, fraction=sample_ratio, seed=42)
        
        # Combine datasets
        df = fraud_df.union(normal_sampled)
        logger.info(f"Balanced dataset size: {df.count()}")
        
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
                numTrees=200,  # Increase for better performance
                maxDepth=15,   # Deeper trees for complex patterns
                minInstancesPerNode=5,
                seed=42
            )
        else:  # logistic_regression
            classifier = LogisticRegression(
                featuresCol="features",
                labelCol="label",
                maxIter=100,
                regParam=0.01,
                elasticNetParam=0.1  # L1 + L2 regularization
            )
        
        # Create pipeline
        pipeline = Pipeline(stages=[assembler, scaler, classifier])
        
        # Start MLflow run
        with mlflow.start_run(run_name=f"fraud_detection_{algorithm}"):
            
            # Log parameters
            if algorithm == "random_forest":
                mlflow.log_param("num_trees", 200)
                mlflow.log_param("max_depth", 15)
                mlflow.log_param("min_instances_per_node", 5)
            else:
                mlflow.log_param("max_iter", 100)
                mlflow.log_param("reg_param", 0.01)
                mlflow.log_param("elastic_net_param", 0.1)
                
            mlflow.log_param("algorithm", algorithm)
            mlflow.log_param("train_samples", train_df.count())
            mlflow.log_param("test_samples", test_df.count())
            
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
            
            # Log metrics
            mlflow.log_metric("auc", auc)
            mlflow.log_metric("accuracy", accuracy)
            mlflow.log_metric("precision", precision)
            mlflow.log_metric("recall", recall)
            mlflow.log_metric("f1_score", f1)
            
            # Log model
            mlflow.spark.log_model(
                model,
                "fraud_detection_model",
                registered_model_name=f"fraud_detection_{algorithm}"
            )
            
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
                mlflow.log_metric("fraud_detection_rate", fraud_detection_rate)
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