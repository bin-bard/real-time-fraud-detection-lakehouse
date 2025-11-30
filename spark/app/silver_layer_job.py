from pyspark.sql import SparkSession
from pyspark.sql.functions import *
from pyspark.sql.types import *
from delta.tables import DeltaTable
import logging
import math

# Cấu hình logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Tính khoảng cách Haversine giữa 2 điểm địa lý (km)
    Formula: https://en.wikipedia.org/wiki/Haversine_formula
    """
    from pyspark.sql.functions import sin, cos, sqrt, atan2, radians, lit
    
    # Earth radius in kilometers
    R = 6371.0
    
    # Convert to radians
    lat1_rad = radians(lat1)
    lon1_rad = radians(lon1)
    lat2_rad = radians(lat2)
    lon2_rad = radians(lon2)
    
    # Haversine formula
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad
    
    a = sin(dlat/2)**2 + cos(lat1_rad) * cos(lat2_rad) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    
    distance = R * c
    return distance

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
    Tạo features cho fraud detection model từ Sparkov dataset
    Dataset columns: trans_date_trans_time, cc_num, merchant, category, amt, first, last, 
                     gender, street, city, state, zip, lat, long, city_pop, job, dob, 
                     trans_num, unix_time, merch_lat, merch_long, is_fraud
    """
    logger.info("Starting feature engineering...")
    
    # Cast amt from String to Double (Debezium encodes as string)
    # Fill NULL với 0.0 để tránh lỗi trong các phép tính sau
    df = df.withColumn("amt", 
                       when(col("amt").isNull(), lit(0.0))
                       .otherwise(col("amt").cast("double")))
    
    # Parse dob: trong Bronze, dob là số ngày kể từ epoch (integer)
    # Convert to date: epoch day 0 = 1970-01-01
    df = df.withColumn("dob_date", 
                       when(col("dob").isNotNull(), 
                            expr("date_add('1970-01-01', CAST(dob AS INT))"))
                       .otherwise(lit(None).cast("date")))
    
    # 1. GEOGRAPHIC FEATURES
    # Khoảng cách Haversine giữa customer location và merchant location
    # Null-safe: chỉ tính khi có đủ 4 tọa độ, otherwise fill -1 để đánh dấu missing
    # Lý do dùng -1 thay vì null: model có thể học pattern "không có thông tin vị trí"
    df = df.withColumn("distance_km", 
                       when((col("lat").isNotNull()) & (col("long").isNotNull()) & 
                            (col("merch_lat").isNotNull()) & (col("merch_long").isNotNull()),
                            haversine_distance(col("lat"), col("long"), 
                                             col("merch_lat"), col("merch_long")))
                       .otherwise(lit(-1.0)))
    
    # 2. DEMOGRAPHIC FEATURES  
    # Tuổi khách hàng
    # Null-safe: fill -1 nếu không có dob (model học pattern "unknown age")
    df = df.withColumn("age", 
                       when((col("trans_timestamp").isNotNull()) & (col("dob_date").isNotNull()),
                            floor(datediff(col("trans_timestamp"), col("dob_date")) / 365.25))
                       .otherwise(lit(-1)))
    
    # 3. TIME FEATURES
    # Thời gian trong ngày, ngày trong tuần
    # Xử lý NULL cho trans_timestamp
    df = df.withColumn("hour", 
                       when(col("trans_timestamp").isNotNull(), hour(col("trans_timestamp")))
                       .otherwise(lit(0)))
    df = df.withColumn("day_of_week", 
                       when(col("trans_timestamp").isNotNull(), dayofweek(col("trans_timestamp")))
                       .otherwise(lit(1)))
    df = df.withColumn("is_weekend", 
                       when((col("day_of_week") == 1) | (col("day_of_week") == 7), 1).otherwise(0))
    
    # Cyclic encoding cho hour (để model hiểu 23h gần 0h)
    df = df.withColumn("hour_sin", sin(col("hour") * 2 * 3.14159 / 24))
    df = df.withColumn("hour_cos", cos(col("hour") * 2 * 3.14159 / 24))
    
    # 4. TRANSACTION AMOUNT FEATURES
    # amt đã được đảm bảo not null ở trên
    df = df.withColumn("log_amount", log(col("amt") + 1))
    df = df.withColumn("is_zero_amount", when(col("amt") == 0, 1).otherwise(0))
    df = df.withColumn("is_high_amount", when(col("amt") > 500, 1).otherwise(0))
    
    # Amount bins cho categorical analysis
    df = df.withColumn("amount_bin",
                       when(col("amt") == 0, 0)
                       .when(col("amt") <= 50, 1)
                       .when(col("amt") <= 100, 2)
                       .when(col("amt") <= 250, 3)
                       .when(col("amt") <= 500, 4)
                       .otherwise(5))
    
    # 5. CATEGORICAL ENCODING
    # Gender: M=1, F=0, null/other=0 (assume female as default)
    df = df.withColumn("gender_encoded", when(col("gender") == "M", 1).otherwise(0))
    
    # 6. RISK INDICATORS
    # Transaction xa (>100km có thể đáng ngờ)
    # Null-safe: nếu distance_km = -1 (missing), không đánh dấu là distant
    df = df.withColumn("is_distant_transaction", 
                       when((col("distance_km") > 100) & (col("distance_km") >= 0), 1).otherwise(0))
    
    # Transaction đêm khuya (11PM-5AM) - hour luôn có giá trị (từ trans_timestamp)
    df = df.withColumn("is_late_night",
                       when((col("hour") >= 23) | (col("hour") <= 5), 1).otherwise(0))
    
    # logger.info(f"After transformations count: {df.count()}")  # Cannot use count() in streaming
    
    # Select ALL columns for Silver layer (original + engineered features)
    df_features = df.select(
        # Original identification from Kaggle dataset
        "trans_num", "cc_num", "trans_timestamp",
        
        # Transaction details
        "merchant", "category", "amt", "unix_time",
        
        # Customer info
        "first", "last", "gender", "street", "city", "state", "zip", "job", "dob",
        
        # Geographic data from dataset
        "lat", "long", "city_pop", "merch_lat", "merch_long",
        
        # Target variable
        "is_fraud",
        
        # ENGINEERED FEATURES (features we actually created above)
        # Geographic
        "distance_km", "is_distant_transaction",
        
        # Demographic  
        "age",
        
        # Time features
        "hour", "day_of_week", "is_weekend", "hour_sin", "hour_cos", "is_late_night",
        
        # Amount features
        "log_amount", "is_zero_amount", "is_high_amount", "amount_bin",
        
        # Categorical encoding
        "gender_encoded",
        
        # Metadata
        "ingestion_time",
        
        # Partitioning columns
        year(col("trans_timestamp")).alias("year"),
        month(col("trans_timestamp")).alias("month"),
        dayofmonth(col("trans_timestamp")).alias("day")
    )
    
    # logger.info(f"After select count: {df_features.count()}")  # Cannot use count() in streaming
    logger.info(f"Feature engineering completed. Total features: {len(df_features.columns)}")
    return df_features

def process_bronze_to_silver_streaming():
    """
    Xử lý dữ liệu từ Bronze layer sang Silver layer (STREAMING MODE)
    Tự động xử lý khi có dữ liệu mới từ Bronze
    """
    spark = create_spark_session()
    spark.sparkContext.setLogLevel("WARN")
    
    logger.info("🥈 Starting Bronze to Silver layer STREAMING processing...")
    
    # Đường dẫn
    bronze_path = "s3a://lakehouse/bronze/transactions"
    silver_path = "s3a://lakehouse/silver/transactions"
    checkpoint_path = "s3a://lakehouse/checkpoints/bronze_to_silver"
    
    try:
        # Đọc dữ liệu từ Bronze layer (STREAMING)
        logger.info("Setting up streaming read from Bronze layer...")
        bronze_stream = spark.readStream \
            .format("delta") \
            .load(bronze_path)
        
        logger.info("✅ Streaming source configured")
        
        # Data quality checks
        logger.info("Applying data quality checks and transformations...")
        
        # 1. Loại bỏ các records không thể trace (trans_num hoặc cc_num null)
        # Theo spec: trans_num là mã giao dịch, cc_num là ID khách hàng - cả 2 đều critical
        bronze_stream = bronze_stream.filter(
            col("trans_num").isNotNull() & 
            col("cc_num").isNotNull() &
            col("trans_timestamp").isNotNull()  # Partition key cũng cần có
        )
        
        # 2. Fill null cho các cột quan trọng nhưng có thể thiếu
        # amt: số tiền giao dịch - fill 0 nếu null (giao dịch không hợp lệ nhưng vẫn ghi nhận)
        bronze_stream = bronze_stream.withColumn("amt", coalesce(col("amt"), lit("0")))
        
        # is_fraud: label - fill 0 nếu null (assume normal nếu không có label)
        bronze_stream = bronze_stream.withColumn("is_fraud", coalesce(col("is_fraud"), lit("0")))
        
        # 3. Feature engineering với null-safe logic
        silver_stream = feature_engineering(bronze_stream)
        
        # Ghi vào Silver layer (STREAMING)
        logger.info("Starting streaming write to Silver layer...")
        
        query = silver_stream.writeStream \
            .format("delta") \
            .outputMode("append") \
            .option("checkpointLocation", checkpoint_path) \
            .partitionBy("year", "month", "day") \
            .trigger(processingTime="30 seconds") \
            .start(silver_path)
            
        logger.info("✅ Silver layer streaming job started!")
        logger.info(f"📊 Checkpoint: {checkpoint_path}")
        logger.info(f"📊 Output: {silver_path}")
        logger.info("⏳ Waiting for streaming data (press Ctrl+C to stop)...")
        
        # Chạy liên tục
        query.awaitTermination()
        
    except KeyboardInterrupt:
        logger.info("⚠️ Streaming job stopped by user")
        return True
    except Exception as e:
        logger.error(f"❌ Error in Silver layer streaming: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = process_bronze_to_silver_streaming()
    if not success:
        print("❌ Silver layer streaming failed!")
        exit(1)
    else:
        print("🎉 Silver layer streaming completed!")
