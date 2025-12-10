
from pyspark.sql import SparkSession
from pyspark.sql.functions import *
from delta.tables import DeltaTable
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_spark_session():
    """Khởi tạo Spark Session với Delta Lake"""
    return SparkSession.builder \
        .appName("GoldLayerBatchProcessing") \
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

def process_silver_to_gold_batch():
    """
    Xử lý dữ liệu từ Silver layer sang Gold layer (BATCH MODE)
    Chỉ xử lý data mới từ lần chạy trước
    """
    spark = create_spark_session()
    spark.sparkContext.setLogLevel("WARN")
    
    logger.info("🥇 Starting Silver to Gold layer BATCH processing...")
    
    silver_path = "s3a://lakehouse/silver/transactions"
    gold_base_path = "s3a://lakehouse/gold"
    
    try:
        # Đọc dữ liệu từ Silver layer
        logger.info("Reading from Silver layer...")
        silver_df = spark.read.format("delta").load(silver_path)
        
        # Kiểm tra xem Gold đã tồn tại chưa để chỉ process data mới
        dim_customer_path = f"{gold_base_path}/dim_customer"
        dim_merchant_path = f"{gold_base_path}/dim_merchant"
        dim_time_path = f"{gold_base_path}/dim_time"
        dim_location_path = f"{gold_base_path}/dim_location"
        fact_transactions_path = f"{gold_base_path}/fact_transactions"
        
        try:
            # Lấy timestamp mới nhất trong fact table
            max_timestamp = spark.read.format("delta").load(fact_transactions_path) \
                .agg(max("transaction_timestamp").alias("max_ts")) \
                .collect()[0]["max_ts"]
            
            if max_timestamp:
                logger.info(f"Processing new data after: {max_timestamp}")
                silver_df = silver_df.filter(col("trans_timestamp") > max_timestamp)
            else:
                logger.info("Gold tables empty, processing all Silver data")
        except:
            logger.info("Gold tables don't exist yet, processing all Silver data")
        
        # Kiểm tra có data mới không
        count = silver_df.count()
        logger.info(f"Found {count} new records to process")
        
        if count == 0:
            logger.info("No new data to process. Exiting...")
            return
        
        # ============================================
        # 1. DIM CUSTOMER
        # ============================================
        logger.info("Creating dim_customer...")
        dim_customer = silver_df.select(
            col("cc_num").alias("customer_key"),
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
        
        dim_customer.write \
            .format("delta") \
            .mode("append") \
            .save(dim_customer_path)
        logger.info(f"✅ dim_customer updated: {dim_customer.count()} records")
        
        # ============================================
        # 2. DIM MERCHANT
        # ============================================
        logger.info("Creating dim_merchant...")
        dim_merchant = silver_df.select(
            col("merchant"),
            col("category").alias("merchant_category"),
            col("merch_lat").alias("merchant_lat"),
            col("merch_long").alias("merchant_long")
        ).dropDuplicates(["merchant", "merchant_lat", "merchant_long"]) \
        .withColumn("merchant_key", abs(hash(concat(col("merchant"), col("merchant_lat"), col("merchant_long"))))) \
        .select(
            "merchant_key",
            "merchant",
            "merchant_category",
            "merchant_lat",
            "merchant_long",
            current_timestamp().alias("last_updated")
        )
        
        dim_merchant.write \
            .format("delta") \
            .mode("append") \
            .save(dim_merchant_path)
        logger.info(f"✅ dim_merchant updated: {dim_merchant.count()} records")
        
        # ============================================
        # 3. DIM TIME
        # ============================================
        logger.info("Creating dim_time...")
        dim_time = silver_df.select(
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
            date_format(col("trans_timestamp"), "EEEE").alias("day_name"),
            date_format(col("trans_timestamp"), "MMMM").alias("month_name"),
            when((dayofweek(col("trans_timestamp")) == 1) | 
                 (dayofweek(col("trans_timestamp")) == 7), 1).otherwise(0).alias("is_weekend"),
            when(hour(col("trans_timestamp")).between(6, 11), "Morning")
            .when(hour(col("trans_timestamp")).between(12, 17), "Afternoon")
            .when(hour(col("trans_timestamp")).between(18, 22), "Evening")
            .otherwise("Night").alias("time_period")
        ).dropDuplicates(["time_key"])
        
        dim_time.write \
            .format("delta") \
            .mode("append") \
            .save(dim_time_path)
        logger.info(f"✅ dim_time updated: {dim_time.count()} records")
        
        # ============================================
        # 4. DIM LOCATION
        # ============================================
        logger.info("Creating dim_location...")
        dim_location = silver_df.select(
            col("city"),
            col("state"),
            col("zip"),
            col("lat"),
            col("long"),
            col("city_pop")
        ).dropDuplicates(["city", "state", "zip"]) \
        .withColumn("location_key", abs(hash(concat(col("city"), col("state"), col("zip"))))) \
        .select(
            "location_key",
            "city",
            "state",
            "zip",
            "lat",
            "long",
            "city_pop",
            current_timestamp().alias("last_updated")
        )
        
        dim_location.write \
            .format("delta") \
            .mode("append") \
            .save(dim_location_path)
        logger.info(f"✅ dim_location updated: {dim_location.count()} records")
        
        # ============================================
        # 5. FACT TRANSACTIONS
        # ============================================
        logger.info("Creating fact_transactions...")
        fact_transactions = silver_df.select(
            col("trans_num").alias("transaction_key"),
            col("cc_num").alias("customer_key"),
            col("merchant"),
            date_format(col("trans_timestamp"), "yyyyMMddHH").alias("time_key"),
            col("amt").alias("transaction_amount"),
            col("is_fraud").alias("is_fraud"),
            col("trans_timestamp").alias("transaction_timestamp"),
            col("category").alias("transaction_category"),
            col("unix_time"),
            col("distance_km"),
            col("age").alias("customer_age_at_transaction"),
            col("log_amount"),
            col("amount_bin"),
            col("is_distant_transaction"),
            col("is_late_night"),
            col("is_zero_amount"),
            col("is_high_amount"),
            col("hour").alias("transaction_hour"),
            col("day_of_week").alias("transaction_day_of_week"),
            col("is_weekend").alias("is_weekend_transaction"),
            col("hour_sin"),
            col("hour_cos"),
            col("ingestion_time"),
            current_timestamp().alias("fact_created_time")
        )
        
        fact_transactions.write \
            .format("delta") \
            .mode("append") \
            .save(fact_transactions_path)
        logger.info(f"✅ fact_transactions updated: {fact_transactions.count()} records")
        
        # ============================================
        # SUMMARY
        # ============================================
        logger.info("=" * 60)
        logger.info("✅ Gold layer batch processing completed!")
        logger.info(f"⚡ Processed {count} records from Silver layer")
        logger.info("⚡ Updated tables:")
        logger.info(f"   - dim_customer -> {dim_customer_path}")
        logger.info(f"   - dim_merchant -> {dim_merchant_path}")
        logger.info(f"   - dim_time -> {dim_time_path}")
        logger.info(f"   - dim_location -> {dim_location_path}")
        logger.info(f"   - fact_transactions -> {fact_transactions_path}")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"❌ Error processing Silver to Gold: {e}", exc_info=True)
        raise
    finally:
        spark.stop()

if __name__ == "__main__":
    process_silver_to_gold_batch()
