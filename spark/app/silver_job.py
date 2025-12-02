
import logging
from pyspark.sql import SparkSession
from pyspark.sql.functions import *
from pyspark.sql.types import DoubleType
from delta.tables import DeltaTable
from datetime import datetime
import math

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def create_spark_session():
    """Khởi tạo Spark Session với Delta Lake"""
    return SparkSession.builder \
        .appName("SilverLayerBatchProcessing") \
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
        .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog") \
        .config("spark.hadoop.fs.s3a.endpoint", "http://minio:9000") \
        .config("spark.hadoop.fs.s3a.access.key", "minio") \
        .config("spark.hadoop.fs.s3a.secret.key", "minio123") \
        .config("spark.hadoop.fs.s3a.path.style.access", "true") \
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem") \
        .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false") \
        .config("spark.sql.parquet.datetimeRebaseModeInWrite", "LEGACY") \
        .config("spark.sql.parquet.int96RebaseModeInWrite", "LEGACY") \
        .getOrCreate()

def haversine_distance(lat1, lon1, lat2, lon2):
    """Tính khoảng cách giữa 2 điểm địa lý (km)"""
    R = 6371  # Bán kính trái đất (km)
    
    phi1 = math.radians(lat1) if lat1 is not None else 0
    phi2 = math.radians(lat2) if lat2 is not None else 0
    delta_phi = math.radians(lat2 - lat1) if (lat1 is not None and lat2 is not None) else 0
    delta_lambda = math.radians(lon2 - lon1) if (lon1 is not None and lon2 is not None) else 0
    
    a = math.sin(delta_phi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    
    return R * c

# Đăng ký UDF
haversine_udf = udf(haversine_distance, DoubleType())

def feature_engineering(df):
    """Feature engineering với null-safe logic"""
    logger.info("Starting feature engineering...")
    
    # 1. GEOGRAPHIC FEATURES
    df = df.withColumn("distance_km", 
                       haversine_udf(col("lat"), col("long"), col("merch_lat"), col("merch_long")))
    df = df.withColumn("distance_km", 
                       when(col("distance_km").isNull(), -1).otherwise(col("distance_km")))
    
    # 2. DEMOGRAPHIC FEATURES  
    df = df.withColumn("age", 
                       floor(datediff(col("trans_timestamp"), col("dob")) / 365.25))
    df = df.withColumn("age", 
                       when(col("age").isNull(), -1).otherwise(col("age")))
    
    # 3. TIME FEATURES
    df = df.withColumn("hour", hour(col("trans_timestamp")))
    df = df.withColumn("day_of_week", dayofweek(col("trans_timestamp")))
    df = df.withColumn("is_weekend", 
                       when(col("day_of_week").isin([1, 7]), 1).otherwise(0))
    df = df.withColumn("hour_sin", sin(2 * 3.14159 * col("hour") / 24))
    df = df.withColumn("hour_cos", cos(2 * 3.14159 * col("hour") / 24))
    
    # 4. AMOUNT FEATURES
    df = df.withColumn("log_amount", 
                       when(col("amt") > 0, log1p(col("amt"))).otherwise(0))
    df = df.withColumn("is_zero_amount", when(col("amt") == 0, 1).otherwise(0))
    df = df.withColumn("is_high_amount", when(col("amt") > 500, 1).otherwise(0))
    df = df.withColumn("amount_bin",
                       when(col("amt") < 10, 1)
                       .when((col("amt") >= 10) & (col("amt") < 50), 2)
                       .when((col("amt") >= 50) & (col("amt") < 100), 3)
                       .when((col("amt") >= 100) & (col("amt") < 500), 4)
                       .otherwise(5))
    
    # 5. CATEGORICAL ENCODING
    df = df.withColumn("gender_encoded", when(col("gender") == "M", 1).otherwise(0))
    
    # 6. RISK INDICATORS
    df = df.withColumn("is_distant_transaction", 
                       when((col("distance_km") > 100) & (col("distance_km") >= 0), 1).otherwise(0))
    df = df.withColumn("is_late_night",
                       when((col("hour") >= 23) | (col("hour") <= 5), 1).otherwise(0))
    
    # Partition columns
    df = df.withColumn("year", year(col("trans_timestamp")))
    df = df.withColumn("month", month(col("trans_timestamp")))
    df = df.withColumn("day", dayofmonth(col("trans_timestamp")))
    
    # Timestamp ghi vào Silver
    df = df.withColumn("ingestion_time", current_timestamp())
    
    logger.info("Feature engineering completed. Total features: 40")
    return df

def process_bronze_to_silver_batch():
    """
    Xử lý dữ liệu từ Bronze layer sang Silver layer (BATCH MODE)
    Chỉ xử lý data mới từ lần chạy trước
    """
    spark = create_spark_session()
    spark.sparkContext.setLogLevel("WARN")
    
    logger.info("🥈 Starting Bronze to Silver layer BATCH processing...")
    
    bronze_path = "s3a://lakehouse/bronze/transactions"
    silver_path = "s3a://lakehouse/silver/transactions"
    checkpoint_path = "s3a://lakehouse/checkpoints/bronze_to_silver_batch"
    
    try:
        # Đọc dữ liệu từ Bronze layer
        logger.info("Reading from Bronze layer...")
        bronze_df = spark.read.format("delta").load(bronze_path)
        
        # Kiểm tra xem Silver đã tồn tại chưa
        try:
            silver_table = DeltaTable.forPath(spark, silver_path)
            # Lấy timestamp mới nhất trong Silver
            max_timestamp = spark.read.format("delta").load(silver_path) \
                .agg(max("trans_timestamp").alias("max_ts")) \
                .collect()[0]["max_ts"]
            
            if max_timestamp:
                logger.info(f"Processing new data after: {max_timestamp}")
                bronze_df = bronze_df.filter(col("trans_timestamp") > max_timestamp)
            else:
                logger.info("Silver table empty, processing all Bronze data")
        except:
            logger.info("Silver table doesn't exist yet, processing all Bronze data")
        
        # Kiểm tra có data mới không
        count = bronze_df.count()
        logger.info(f"Found {count} new records to process")
        
        if count == 0:
            logger.info("No new data to process. Exiting...")
            return
        
        # Data quality checks - Bronze Delta đã có data flatten sẵn
        logger.info("Applying data quality checks...")
        bronze_df = bronze_df.filter(col("trans_num").isNotNull())
        
        # Cast types từ String sang đúng type (Bronze lưu String)
        logger.info("Casting data types...")
        bronze_df = bronze_df.select(
            col("trans_date_trans_time"),
            col("cc_num"),
            col("merchant"),
            col("category"),
            col("amt").cast("double"),
            col("first"),
            col("last"),
            col("gender"),
            col("street"),
            col("city"),
            col("state"),
            col("zip"),
            col("lat").cast("double"),
            col("long").cast("double"),
            col("city_pop").cast("long"),
            col("job"),
            col("dob").cast("date"),
            col("trans_num"),
            col("unix_time").cast("long"),
            col("merch_lat").cast("double"),
            col("merch_long").cast("double"),
            col("is_fraud").cast("int"),
            col("trans_timestamp"),
            col("ingestion_time"),
            col("year"),
            col("month"),
            col("day")
        )
        
        # Fill missing values
        bronze_df = bronze_df.fillna({
            "amt": 0.0,
            "first": "Unknown",
            "last": "Unknown",
            "gender": "U",
            "city": "Unknown",
            "state": "Unknown",
            "job": "Unknown",
            "is_fraud": 0
        })
        
        # Feature engineering
        silver_df = feature_engineering(bronze_df)
        
        # Ghi vào Silver layer
        logger.info("Writing to Silver layer...")
        
        # Check và xử lý schema conflict
        try:
            test_df = spark.read.format("delta").load(silver_path).limit(1)
            # Test write với 1 record để phát hiện schema conflict
            try:
                silver_df.limit(0).write.format("delta").mode("append").save(silver_path)
                write_mode = "append"
            except Exception as schema_err:
                if "Failed to merge" in str(schema_err):
                    logger.warning(f"⚠️ Schema conflict detected: {schema_err}")
                    logger.info("🔄 Overwriting Silver table with new schema...")
                    write_mode = "overwrite"
                else:
                    raise schema_err
        except:
            logger.info("Silver table doesn't exist, creating new table...")
            write_mode = "append"
            
        silver_df.write \
            .format("delta") \
            .mode(write_mode) \
            .option("overwriteSchema", "true") \
            .partitionBy("year", "month", "day") \
            .save(silver_path)
            
        logger.info(f"✅ Successfully processed {count} records to Silver layer!")
        logger.info(f"📊 Output: {silver_path}")
        
    except Exception as e:
        logger.error(f"❌ Error processing Bronze to Silver: {e}", exc_info=True)
        raise
    finally:
        spark.stop()

if __name__ == "__main__":
    process_bronze_to_silver_batch()
