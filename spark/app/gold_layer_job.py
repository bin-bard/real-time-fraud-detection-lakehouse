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
        .appName("GoldLayerProcessing") \
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
        .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog") \
        .config("spark.hadoop.fs.s3a.endpoint", "http://minio:9000") \
        .config("spark.hadoop.fs.s3a.access.key", "minio") \
        .config("spark.hadoop.fs.s3a.secret.key", "minio123") \
        .config("spark.hadoop.fs.s3a.path.style.access", "true") \
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem") \
        .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false") \
        .getOrCreate()

def create_fraud_summary():
    """
    Tạo bảng tổng hợp fraud detection metrics
    """
    spark = create_spark_session()
    spark.sparkContext.setLogLevel("WARN")
    
    logger.info("🥇 Creating fraud summary for Gold layer...")
    
    silver_path = "s3a://lakehouse/silver/transactions"
    gold_aggregated_path = "s3a://lakehouse/gold/aggregated"
    
    try:
        # Đọc dữ liệu từ Silver layer
        df = spark.read.format("delta").load(silver_path)
        
        # Fraud summary by day
        daily_summary = df.groupBy("year", "month", "day") \
            .agg(
                count("*").alias("total_transactions"),
                sum(when(col("is_fraud") == "1", 1).otherwise(0)).alias("fraud_transactions"),
                sum(when(col("is_fraud") == "0", 1).otherwise(0)).alias("normal_transactions"),
                avg("amt").alias("avg_transaction_amount"),
                max("amt").alias("max_transaction_amount"),
                min("amt").alias("min_transaction_amount"),
                sum("amt").alias("total_amount"),
                sum(when(col("is_fraud") == "1", col("amt")).otherwise(0)).alias("fraud_amount"),
                avg("distance_km").alias("avg_distance"),
                max("distance_km").alias("max_distance")
            ) \
            .withColumn("fraud_rate", col("fraud_transactions") / col("total_transactions")) \
            .withColumn("avg_fraud_amount", 
                       when(col("fraud_transactions") > 0, col("fraud_amount") / col("fraud_transactions"))
                       .otherwise(0)) \
            .withColumn("report_date", 
                       concat(col("year"), lit("-"), 
                             lpad(col("month"), 2, "0"), lit("-"),
                             lpad(col("day"), 2, "0")))
        
        # Hourly analysis
        hourly_summary = df.groupBy("year", "month", "day", "hour") \
            .agg(
                count("*").alias("total_transactions"),
                sum(when(col("is_fraud") == "1", 1).otherwise(0)).alias("fraud_transactions"),
                avg("amt").alias("avg_amount"),
                avg("distance_km").alias("avg_distance")
            ) \
            .withColumn("fraud_rate", col("fraud_transactions") / col("total_transactions"))
        
        # Amount range analysis  
        amount_ranges = df.withColumn(
            "amount_range",
            when(col("amt") == 0, "zero")
            .when(col("amt") <= 50, "low")
            .when(col("amt") <= 250, "medium")
            .when(col("amt") <= 500, "high")
            .otherwise("very_high")
        )
        
        amount_summary = amount_ranges.groupBy("amount_range") \
            .agg(
                count("*").alias("total_transactions"),
                sum(when(col("is_fraud") == "1", 1).otherwise(0)).alias("fraud_transactions"),
                avg("amt").alias("avg_amount")
            ) \
            .withColumn("fraud_rate", col("fraud_transactions") / col("total_transactions"))
        
        # Geographic analysis (by state)
        state_summary = df.groupBy("state") \
            .agg(
                count("*").alias("total_transactions"),
                sum(when(col("is_fraud") == "1", 1).otherwise(0)).alias("fraud_transactions"),
                avg("amt").alias("avg_amount"),
                avg("distance_km").alias("avg_distance")
            ) \
            .withColumn("fraud_rate", col("fraud_transactions") / col("total_transactions")) \
            .orderBy(desc("fraud_transactions"))
        
        # Category analysis
        category_summary = df.groupBy("category") \
            .agg(
                count("*").alias("total_transactions"),
                sum(when(col("is_fraud") == "1", 1).otherwise(0)).alias("fraud_transactions"),
                avg("amt").alias("avg_amount")
            ) \
            .withColumn("fraud_rate", col("fraud_transactions") / col("total_transactions")) \
            .orderBy(desc("fraud_rate"))
        
        # Ghi các bảng tổng hợp
        logger.info("Writing daily summary to Gold layer...")
        daily_summary.write \
            .format("delta") \
            .mode("overwrite") \
            .option("path", f"{gold_aggregated_path}/daily_summary") \
            .partitionBy("year", "month") \
            .save()
        
        logger.info("Writing hourly summary to Gold layer...")
        hourly_summary.write \
            .format("delta") \
            .mode("overwrite") \
            .option("path", f"{gold_aggregated_path}/hourly_summary") \
            .partitionBy("year", "month", "day") \
            .save()
        
        logger.info("Writing amount summary to Gold layer...")
        amount_summary.write \
            .format("delta") \
            .mode("overwrite") \
            .option("path", f"{gold_aggregated_path}/amount_summary") \
            .save()
        
        logger.info("Writing state summary to Gold layer...")
        state_summary.write \
            .format("delta") \
            .mode("overwrite") \
            .option("path", f"{gold_aggregated_path}/state_summary") \
            .save()
        
        logger.info("Writing category summary to Gold layer...")
        category_summary.write \
            .format("delta") \
            .mode("overwrite") \
            .option("path", f"{gold_aggregated_path}/category_summary") \
            .save()
        
        # In metrics
        logger.info("📊 Gold Layer Summary Created:")
        logger.info(f"   Daily summary records: {daily_summary.count()}")
        logger.info(f"   Hourly summary records: {hourly_summary.count()}")
        logger.info(f"   Amount range records: {amount_summary.count()}")
        logger.info(f"   State summary records: {state_summary.count()}")
        logger.info(f"   Category summary records: {category_summary.count()}")
        
        # Show sample data
        logger.info("📋 Sample Daily Summary:")
        daily_summary.orderBy(desc("report_date")).show(5, truncate=False)
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error creating Gold layer: {str(e)}")
        return False
    finally:
        spark.stop()

def create_real_time_metrics():
    """
    Tạo metrics cho real-time monitoring
    """
    spark = create_spark_session()
    spark.sparkContext.setLogLevel("WARN")
    
    logger.info("📈 Creating real-time metrics...")
    
    silver_path = "s3a://lakehouse/silver/transactions"
    gold_reports_path = "s3a://lakehouse/gold/reports"
    
    try:
        df = spark.read.format("delta").load(silver_path)
        
        # Latest metrics (last 24 hours simulation)
        latest_metrics = df.filter(col("day") == dayofmonth(current_date())) \
            .agg(
                count("*").alias("total_transactions_today"),
                sum(when(col("is_fraud") == "1", 1).otherwise(0)).alias("fraud_detected_today"),
                avg("amt").alias("avg_amount_today"),
                avg("distance_km").alias("avg_distance_today"),
                max("ingestion_time").alias("last_update")
            ) \
            .withColumn("fraud_rate_today", col("fraud_detected_today") / col("total_transactions_today")) \
            .withColumn("alert_level",
                       when(col("fraud_rate_today") > 0.01, "HIGH")
                       .when(col("fraud_rate_today") > 0.005, "MEDIUM")
                       .otherwise("LOW"))
        
        # Top fraud patterns
        fraud_patterns = df.filter(col("is_fraud") == "1") \
            .withColumn(
                "amount_range",
                when(col("amt") == 0, "zero")
                .when(col("amt") <= 50, "low")
                .when(col("amt") <= 250, "medium")
                .when(col("amt") <= 500, "high")
                .otherwise("very_high")
            ) \
            .groupBy("amount_range") \
            .agg(
                count("*").alias("fraud_count"),
                avg("amt").alias("avg_fraud_amount"),
                avg("distance_km").alias("avg_fraud_distance")
            ) \
            .orderBy(desc("fraud_count"))
        
        # Ghi reports
        logger.info("Writing real-time metrics...")
        latest_metrics.write \
            .format("delta") \
            .mode("overwrite") \
            .option("path", f"{gold_reports_path}/latest_metrics") \
            .save()
        
        fraud_patterns.write \
            .format("delta") \
            .mode("overwrite") \
            .option("path", f"{gold_reports_path}/fraud_patterns") \
            .save()
        
        logger.info("✅ Real-time metrics created successfully!")
        
        # Show current metrics
        logger.info("📊 Current Metrics:")
        latest_metrics.show(truncate=False)
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error creating real-time metrics: {str(e)}")
        return False
    finally:
        spark.stop()

if __name__ == "__main__":
    logger.info("🚀 Starting Gold layer processing...")
    
    # Create aggregated summaries
    if create_fraud_summary():
        logger.info("✅ Fraud summary created")
    else:
        logger.error("❌ Failed to create fraud summary")
    
    # Create real-time metrics
    if create_real_time_metrics():
        logger.info("✅ Real-time metrics created")
    else:
        logger.error("❌ Failed to create real-time metrics")
    
    logger.info("🎉 Gold layer processing completed!")