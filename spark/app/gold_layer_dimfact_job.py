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
        .appName("GoldLayerDimFactProcessing") \
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
        .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog") \
        .config("spark.hadoop.fs.s3a.endpoint", "http://minio:9000") \
        .config("spark.hadoop.fs.s3a.access.key", "minio") \
        .config("spark.hadoop.fs.s3a.secret.key", "minio123") \
        .config("spark.hadoop.fs.s3a.path.style.access", "true") \
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem") \
        .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false") \
        .getOrCreate()

def create_dim_customer(df):
    """
    Tạo bảng dimension Customer
    SCD Type 1 (overwrite với thông tin mới nhất)
    """
    logger.info("Creating dim_customer...")
    
    dim_customer = df.select(
        col("cc_num").alias("customer_key"),  # Surrogate key = cc_num
        col("first").alias("first_name"),
        col("last").alias("last_name"),
        col("gender"),
        col("dob").alias("date_of_birth"),
        col("age"),
        col("street"),
        col("city").alias("customer_city"),
        col("state").alias("customer_state"),
        col("zip").alias("customer_zip"),
        col("lat").alias("customer_lat"),
        col("long").alias("customer_long"),
        col("city_pop").alias("customer_city_population"),
        col("job"),
        current_timestamp().alias("last_updated")
    ).dropDuplicates(["customer_key"])
    
    return dim_customer

def create_dim_merchant(df):
    """
    Tạo bảng dimension Merchant
    """
    logger.info("Creating dim_merchant...")
    
    # Tạo merchant_key từ merchant name + location
    dim_merchant = df.select(
        col("merchant"),
        col("category").alias("merchant_category"),
        col("merch_lat").alias("merchant_lat"),
        col("merch_long").alias("merchant_long")
    ).dropDuplicates(["merchant", "merchant_lat", "merchant_long"])
    
    # Tạo surrogate key
    dim_merchant = dim_merchant.withColumn(
        "merchant_key",
        monotonically_increasing_id()
    ).select(
        "merchant_key",
        "merchant",
        "merchant_category",
        "merchant_lat",
        "merchant_long",
        current_timestamp().alias("last_updated")
    )
    
    return dim_merchant

def create_dim_time(df):
    """
    Tạo bảng dimension Time
    Chi tiết thời gian cho phân tích
    """
    logger.info("Creating dim_time...")
    
    dim_time = df.select(
        col("trans_timestamp")
    ).dropDuplicates()
    
    dim_time = dim_time.select(
        date_format(col("trans_timestamp"), "yyyyMMddHH").alias("time_key"),
        col("trans_timestamp").alias("full_timestamp"),
        year(col("trans_timestamp")).alias("year"),
        month(col("trans_timestamp")).alias("month"),
        dayofmonth(col("trans_timestamp")).alias("day"),
        hour(col("trans_timestamp")).alias("hour"),
        minute(col("trans_timestamp")).alias("minute"),
        dayofweek(col("trans_timestamp")).alias("day_of_week"),
        weekofyear(col("trans_timestamp")).alias("week_of_year"),
        quarter(col("trans_timestamp")).alias("quarter"),
        # Day name
        date_format(col("trans_timestamp"), "EEEE").alias("day_name"),
        # Month name
        date_format(col("trans_timestamp"), "MMMM").alias("month_name"),
        # Is weekend
        when((dayofweek(col("trans_timestamp")) == 1) | 
             (dayofweek(col("trans_timestamp")) == 7), 1).otherwise(0).alias("is_weekend"),
        # Time period
        when(hour(col("trans_timestamp")).between(6, 11), "Morning")
        .when(hour(col("trans_timestamp")).between(12, 17), "Afternoon")
        .when(hour(col("trans_timestamp")).between(18, 22), "Evening")
        .otherwise("Night").alias("time_period")
    )
    
    return dim_time

def create_dim_location(df):
    """
    Tạo bảng dimension Location (customer location)
    """
    logger.info("Creating dim_location...")
    
    dim_location = df.select(
        col("city"),
        col("state"),
        col("zip"),
        col("lat"),
        col("long"),
        col("city_pop")
    ).dropDuplicates(["city", "state", "zip"])
    
    dim_location = dim_location.withColumn(
        "location_key",
        monotonically_increasing_id()
    ).select(
        "location_key",
        "city",
        "state",
        "zip",
        "lat",
        "long",
        "city_pop",
        current_timestamp().alias("last_updated")
    )
    
    return dim_location

def create_fact_transactions(df, dim_merchant):
    """
    Tạo bảng fact Transactions
    Chứa các metrics và foreign keys đến dimensions
    """
    logger.info("Creating fact_transactions...")
    
    # Join với dim_merchant để lấy merchant_key
    fact = df.alias("t").join(
        dim_merchant.alias("m"),
        (col("t.merchant") == col("m.merchant")) &
        (col("t.merch_lat") == col("m.merchant_lat")) &
        (col("t.merch_long") == col("m.merchant_long")),
        "left"
    )
    
    fact_transactions = fact.select(
        # Surrogate key
        col("t.trans_num").alias("transaction_key"),
        
        # Foreign keys to dimensions
        col("t.cc_num").alias("customer_key"),
        col("m.merchant_key"),
        date_format(col("t.trans_timestamp"), "yyyyMMddHH").alias("time_key"),
        
        # Transaction facts/measures
        col("t.amt").alias("transaction_amount"),
        col("t.is_fraud").alias("is_fraud"),
        
        # Degenerate dimensions (transaction details)
        col("t.trans_timestamp").alias("transaction_timestamp"),
        col("t.category").alias("transaction_category"),
        col("t.unix_time"),
        
        # Calculated measures from Silver layer
        col("t.distance_km"),
        col("t.age").alias("customer_age_at_transaction"),
        col("t.log_amount"),
        col("t.amount_bin"),
        
        # Risk indicators (measures/flags)
        col("t.is_distant_transaction"),
        col("t.is_late_night"),
        col("t.is_zero_amount"),
        col("t.is_high_amount"),
        
        # Time features
        col("t.hour").alias("transaction_hour"),
        col("t.day_of_week").alias("transaction_day_of_week"),
        col("t.is_weekend").alias("is_weekend_transaction"),
        col("t.hour_sin"),
        col("t.hour_cos"),
        
        # Metadata
        col("t.ingestion_time"),
        current_timestamp().alias("fact_created_time")
    )
    
    return fact_transactions

def process_silver_to_gold_dimfact():
    """
    Xử lý dữ liệu từ Silver layer sang Gold layer với mô hình Dimensional
    """
    spark = create_spark_session()
    spark.sparkContext.setLogLevel("WARN")
    
    logger.info("🥇 Starting Silver to Gold layer (Dim/Fact) processing...")
    
    # Đường dẫn
    silver_path = "s3a://lakehouse/silver/transactions"
    gold_base_path = "s3a://lakehouse/gold"
    
    try:
        # Đọc dữ liệu từ Silver layer
        logger.info("Reading from Silver layer...")
        silver_df = spark.read.format("delta").load(silver_path)
        
        record_count = silver_df.count()
        logger.info(f"Silver data count: {record_count}")
        
        if record_count == 0:
            logger.warning("⚠️ No data in Silver layer to process!")
            return False
        
        # ============================================
        # TẠO CÁC DIMENSION TABLES
        # ============================================
        
        # 1. Dim Customer
        dim_customer = create_dim_customer(silver_df)
        dim_customer_path = f"{gold_base_path}/dim_customer"
        logger.info(f"Writing dim_customer ({dim_customer.count()} records)...")
        dim_customer.write \
            .format("delta") \
            .mode("overwrite") \
            .option("overwriteSchema", "true") \
            .save(dim_customer_path)
        logger.info("✅ dim_customer created!")
        
        # 2. Dim Merchant
        dim_merchant = create_dim_merchant(silver_df)
        dim_merchant_path = f"{gold_base_path}/dim_merchant"
        logger.info(f"Writing dim_merchant ({dim_merchant.count()} records)...")
        dim_merchant.write \
            .format("delta") \
            .mode("overwrite") \
            .option("overwriteSchema", "true") \
            .save(dim_merchant_path)
        logger.info("✅ dim_merchant created!")
        
        # 3. Dim Time
        dim_time = create_dim_time(silver_df)
        dim_time_path = f"{gold_base_path}/dim_time"
        logger.info(f"Writing dim_time ({dim_time.count()} records)...")
        dim_time.write \
            .format("delta") \
            .mode("overwrite") \
            .option("overwriteSchema", "true") \
            .save(dim_time_path)
        logger.info("✅ dim_time created!")
        
        # 4. Dim Location
        dim_location = create_dim_location(silver_df)
        dim_location_path = f"{gold_base_path}/dim_location"
        logger.info(f"Writing dim_location ({dim_location.count()} records)...")
        dim_location.write \
            .format("delta") \
            .mode("overwrite") \
            .option("overwriteSchema", "true") \
            .save(dim_location_path)
        logger.info("✅ dim_location created!")
        
        # ============================================
        # TẠO FACT TABLE
        # ============================================
        
        # 5. Fact Transactions
        fact_transactions = create_fact_transactions(silver_df, dim_merchant)
        fact_transactions_path = f"{gold_base_path}/fact_transactions"
        logger.info(f"Writing fact_transactions ({fact_transactions.count()} records)...")
        fact_transactions.write \
            .format("delta") \
            .mode("overwrite") \
            .option("overwriteSchema", "true") \
            .save(fact_transactions_path)
        logger.info("✅ fact_transactions created!")
        
        # ============================================
        # SUMMARY
        # ============================================
        
        logger.info("=" * 60)
        logger.info("✅ Gold layer (Dimensional Model) processing completed!")
        logger.info(f"📊 Dimension Tables Created:")
        logger.info(f"   - dim_customer: {dim_customer.count()} records")
        logger.info(f"   - dim_merchant: {dim_merchant.count()} records")
        logger.info(f"   - dim_time: {dim_time.count()} records")
        logger.info(f"   - dim_location: {dim_location.count()} records")
        logger.info(f"📊 Fact Table Created:")
        logger.info(f"   - fact_transactions: {fact_transactions.count()} records")
        logger.info("=" * 60)
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error in Gold layer processing: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        spark.stop()

if __name__ == "__main__":
    success = process_silver_to_gold_dimfact()
    if success:
        print("🎉 Gold layer (Dim/Fact) processing completed successfully!")
    else:
        print("❌ Gold layer (Dim/Fact) processing failed!")
        exit(1)
