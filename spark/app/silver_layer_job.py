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
    
    logger.info(f"After transformations count: {df.count()}")
    
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
    
    logger.info(f"After select count: {df_features.count()}")
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
        
        # 1. Loại bỏ các records không thể trace (trans_num hoặc cc_num null)
        # Theo spec: trans_num là mã giao dịch, cc_num là ID khách hàng - cả 2 đều critical
        bronze_df = bronze_df.filter(
            col("trans_num").isNotNull() & 
            col("cc_num").isNotNull() &
            col("trans_timestamp").isNotNull()  # Partition key cũng cần có
        )
        logger.info(f"After filtering null critical fields: {bronze_df.count()} records")
        
        # 2. Loại bỏ duplicates based on trans_num
        bronze_df = bronze_df.dropDuplicates(["trans_num"])
        logger.info(f"After deduplication: {bronze_df.count()} records")
        
        # 3. Fill null cho các cột quan trọng nhưng có thể thiếu
        # amt: số tiền giao dịch - fill 0 nếu null (giao dịch không hợp lệ nhưng vẫn ghi nhận)
        bronze_df = bronze_df.withColumn("amt", coalesce(col("amt"), lit("0")))
        
        # is_fraud: label - fill 0 nếu null (assume normal nếu không có label)
        bronze_df = bronze_df.withColumn("is_fraud", coalesce(col("is_fraud"), lit("0")))
        
        # lat, long, merch_lat, merch_long: vị trí - giữ null, sẽ xử lý trong feature engineering
        # Lý do: null ở đây có ý nghĩa (không có thông tin vị trí) vs fillna sai thông tin
        
        # 4. Feature engineering với null-safe logic
        silver_df = feature_engineering(bronze_df)
        
        # Ghi vào Silver layer
        logger.info("Writing to Silver layer...")
        
        # Debug: count before write
        record_count = silver_df.count()
        logger.info(f"Records to write: {record_count}")
        
        if record_count == 0:
            logger.error("❌ No records to write to Silver layer!")
            return False
        
        silver_df.write \
            .format("delta") \
            .mode("overwrite") \
            .partitionBy("year", "month", "day") \
            .option("overwriteSchema", "true") \
            .option("mergeSchema", "true") \
            .save(silver_path)
            
        logger.info("✅ Silver layer processing completed successfully!")
        logger.info(f"📊 Total records written: {record_count}")
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