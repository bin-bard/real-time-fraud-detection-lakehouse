from pyspark.sql import SparkSession
from pyspark.sql.functions import *
from pyspark.sql.types import *
from delta.tables import DeltaTable
import logging

# Cấu hình logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_spark_session():
    """Khởi tạo Spark Session với Delta Lake"""
    return SparkSession.builder \
        .appName("SilverLayerProcessing") \
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
        .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog") \
        .config("spark.hadoop.fs.s3a.endpoint", "http://minio:9000") \
        .config("spark.hadoop.fs.s3a.access.key", "minio") \
        .config("spark.hadoop.fs.s3a.secret.key", "minio123") \
        .config("spark.hadoop.fs.s3a.path.style.access", "true") \
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem") \
        .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false") \
        .getOrCreate()

def feature_engineering(df):
    """
    Tạo features cho fraud detection model
    """
    logger.info("Starting feature engineering...")
    
    # Basic features
    df_features = df.select(
        # Original features
        "Time", "Amount", "Class",
        *[f"V{i}" for i in range(1, 29)],
        "ingestion_time",
        
        # Engineered features
        log(col("Amount") + 1).alias("log_amount"),
        when(col("Amount") == 0, 1).otherwise(0).alias("is_zero_amount"),
        when(col("Amount") > 1000, 1).otherwise(0).alias("is_high_amount"),
        
        # Time-based features  
        hour(col("ingestion_time")).alias("hour_of_day"),
        dayofweek(col("ingestion_time")).alias("day_of_week"),
        
        # Statistical features
        (col("Amount") / (abs(col("V1")) + 1)).alias("amount_v1_ratio"),
        (col("V1") * col("V2")).alias("v1_v2_interaction"),
        
        # Partitioning columns
        year(col("ingestion_time")).alias("year"),
        month(col("ingestion_time")).alias("month"), 
        dayofmonth(col("ingestion_time")).alias("day")
    )
    
    logger.info(f"Feature engineering completed. Total features: {len(df_features.columns)}")
    return df_features

def process_bronze_to_silver():
    """
    Xử lý dữ liệu từ Bronze layer sang Silver layer
    """
    spark = create_spark_session()
    spark.sparkContext.setLogLevel("WARN")
    
    logger.info("🥈 Starting Bronze to Silver layer processing...")
    
    # Đường dẫn
    bronze_path = "s3a://lakehouse/bronze/transactions"
    silver_path = "s3a://lakehouse/silver/transactions"
    
    try:
        # Đọc dữ liệu từ Bronze layer
        logger.info("Reading from Bronze layer...")
        bronze_df = spark.read.format("delta").load(bronze_path)
        
        logger.info(f"Bronze data count: {bronze_df.count()}")
        
        # Data quality checks
        logger.info("Performing data quality checks...")
        
        # Loại bỏ duplicates
        bronze_df = bronze_df.dropDuplicates()
        
        # Loại bỏ null values trong columns quan trọng
        bronze_df = bronze_df.filter(
            col("Amount").isNotNull() & 
            col("Class").isNotNull() &
            col("Time").isNotNull()
        )
        
        # Feature engineering
        silver_df = feature_engineering(bronze_df)
        
        # Ghi vào Silver layer
        logger.info("Writing to Silver layer...")
        
        silver_df.write \
            .format("delta") \
            .mode("overwrite") \
            .option("path", silver_path) \
            .partitionBy("year", "month", "day") \
            .save()
            
        logger.info("✅ Silver layer processing completed successfully!")
        
        # In thống kê
        fraud_count = silver_df.filter(col("Class") == 1).count()
        normal_count = silver_df.filter(col("Class") == 0).count()
        total_count = silver_df.count()
        
        logger.info(f"📊 Silver Layer Statistics:")
        logger.info(f"   Total transactions: {total_count}")
        logger.info(f"   Normal transactions: {normal_count} ({normal_count/total_count*100:.2f}%)")
        logger.info(f"   Fraudulent transactions: {fraud_count} ({fraud_count/total_count*100:.4f}%)")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error in Silver layer processing: {str(e)}")
        return False
    finally:
        spark.stop()

if __name__ == "__main__":
    success = process_bronze_to_silver()
    if success:
        print("🎉 Silver layer processing completed successfully!")
    else:
        print("❌ Silver layer processing failed!")
        exit(1)