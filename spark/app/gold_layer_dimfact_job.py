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

def process_silver_to_gold_dimfact_streaming():
    """
    Xử lý dữ liệu từ Silver layer sang Gold layer với mô hình Dimensional (STREAMING MODE)
    Tự động xử lý khi có dữ liệu mới từ Silver
    """
    spark = create_spark_session()
    spark.sparkContext.setLogLevel("WARN")
    
    logger.info("🥇 Starting Silver to Gold layer (Dim/Fact) STREAMING processing...")
    
    # Đường dẫn
    silver_path = "s3a://lakehouse/silver/transactions"
    gold_base_path = "s3a://lakehouse/gold"
    checkpoint_base = "s3a://lakehouse/checkpoints/silver_to_gold"
    
    try:
        # Đọc dữ liệu từ Silver layer (STREAMING)
        logger.info("Setting up streaming read from Silver layer...")
        silver_stream = spark.readStream \
            .format("delta") \
            .load(silver_path)
        
        logger.info("✅ Streaming source configured")
        
        # ============================================
        # TẠO CÁC DIMENSION TABLES (STREAMING)
        # ============================================
        
        # 1. Dim Customer - Deduplicate by customer_key
        logger.info("Creating streaming dim_customer...")
        dim_customer_stream = silver_stream.select(
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
        
        dim_customer_path = f"{gold_base_path}/dim_customer"
        query_customer = dim_customer_stream.writeStream \
            .format("delta") \
            .outputMode("append") \
            .option("checkpointLocation", f"{checkpoint_base}/dim_customer") \
            .trigger(processingTime="30 seconds") \
            .start(dim_customer_path)
        logger.info(f"✅ dim_customer streaming started -> {dim_customer_path}")
        
        # 2. Dim Merchant
        logger.info("Creating streaming dim_merchant...")
        dim_merchant_stream = silver_stream.select(
            col("merchant"),
            col("category").alias("merchant_category"),
            col("merch_lat").alias("merchant_lat"),
            col("merch_long").alias("merchant_long")
        ).dropDuplicates(["merchant", "merchant_lat", "merchant_long"]) \
        .withColumn("merchant_key", monotonically_increasing_id()) \
        .select(
            "merchant_key",
            "merchant",
            "merchant_category",
            "merchant_lat",
            "merchant_long",
            current_timestamp().alias("last_updated")
        )
        
        dim_merchant_path = f"{gold_base_path}/dim_merchant"
        query_merchant = dim_merchant_stream.writeStream \
            .format("delta") \
            .outputMode("append") \
            .option("checkpointLocation", f"{checkpoint_base}/dim_merchant") \
            .trigger(processingTime="30 seconds") \
            .start(dim_merchant_path)
        logger.info(f"✅ dim_merchant streaming started -> {dim_merchant_path}")
        
        # 3. Dim Time
        logger.info("Creating streaming dim_time...")
        dim_time_stream = silver_stream.select(
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
        
        dim_time_path = f"{gold_base_path}/dim_time"
        query_time = dim_time_stream.writeStream \
            .format("delta") \
            .outputMode("append") \
            .option("checkpointLocation", f"{checkpoint_base}/dim_time") \
            .trigger(processingTime="30 seconds") \
            .start(dim_time_path)
        logger.info(f"✅ dim_time streaming started -> {dim_time_path}")
        
        # 4. Dim Location
        logger.info("Creating streaming dim_location...")
        dim_location_stream = silver_stream.select(
            col("city"),
            col("state"),
            col("zip"),
            col("lat"),
            col("long"),
            col("city_pop")
        ).dropDuplicates(["city", "state", "zip"]) \
        .withColumn("location_key", monotonically_increasing_id()) \
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
        
        dim_location_path = f"{gold_base_path}/dim_location"
        query_location = dim_location_stream.writeStream \
            .format("delta") \
            .outputMode("append") \
            .option("checkpointLocation", f"{checkpoint_base}/dim_location") \
            .trigger(processingTime="30 seconds") \
            .start(dim_location_path)
        logger.info(f"✅ dim_location streaming started -> {dim_location_path}")
        
        # ============================================
        # TẠO FACT TABLE (STREAMING)
        # ============================================
        
        logger.info("Creating streaming fact_transactions...")
        # Note: Trong streaming, không thể join với dim_merchant được tạo động
        # Sử dụng merchant name trực tiếp, merchant_key sẽ được tạo sau qua batch job
        fact_transactions_stream = silver_stream.select(
            col("trans_num").alias("transaction_key"),
            col("cc_num").alias("customer_key"),
            col("merchant"),  # Thay vì merchant_key
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
        
        fact_transactions_path = f"{gold_base_path}/fact_transactions"
        query_fact = fact_transactions_stream.writeStream \
            .format("delta") \
            .outputMode("append") \
            .option("checkpointLocation", f"{checkpoint_base}/fact_transactions") \
            .trigger(processingTime="30 seconds") \
            .start(fact_transactions_path)
        logger.info(f"✅ fact_transactions streaming started -> {fact_transactions_path}")
        
        # ============================================
        # WAIT FOR ALL STREAMS
        # ============================================
        
        logger.info("=" * 60)
        logger.info("✅ All Gold layer streaming jobs started!")
        logger.info(f"📊 Dimension Tables (Streaming):")
        logger.info(f"   - dim_customer -> {dim_customer_path}")
        logger.info(f"   - dim_merchant -> {dim_merchant_path}")
        logger.info(f"   - dim_time -> {dim_time_path}")
        logger.info(f"   - dim_location -> {dim_location_path}")
        logger.info(f"📊 Fact Table (Streaming):")
        logger.info(f"   - fact_transactions -> {fact_transactions_path}")
        logger.info("=" * 60)
        logger.info("⏳ All streams running... (press Ctrl+C to stop)")
        
        # Wait for all queries
        spark.streams.awaitAnyTermination()
        
    except KeyboardInterrupt:
        logger.info("⚠️ Streaming jobs stopped by user")
        return True
    except Exception as e:
        logger.error(f"❌ Error in Gold layer streaming: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = process_silver_to_gold_dimfact_streaming()
    if not success:
        print("❌ Gold layer (Dim/Fact) streaming failed!")
        exit(1)
    else:
        print("🎉 Gold layer (Dim/Fact) streaming completed!")

