from pyspark.sql import SparkSession
from pyspark.sql.functions import from_json, col, current_timestamp, year, month, dayofmonth
from pyspark.sql.types import StructType, StructField, StringType, DoubleType

# Cấu hình Kafka
KAFKA_BROKER = "kafka:9092"
KAFKA_TOPIC = "credit_card_transactions"

# MinIO S3 paths
BRONZE_PATH = "s3a://lakehouse/bronze/transactions"
SILVER_PATH = "s3a://lakehouse/silver/transactions"

# Khởi tạo Spark Session với Delta Lake (không dùng configure_spark_with_delta_pip)
spark = SparkSession.builder \
    .appName("RealTimeFraudDetection") \
    .config("spark.jars.packages", 
             "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0," +
             "io.delta:delta-core_2.12:2.4.0," +
             "org.apache.hadoop:hadoop-aws:3.3.4") \
    .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
    .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog") \
    .config("spark.hadoop.fs.s3a.endpoint", "http://minio:9000") \
    .config("spark.hadoop.fs.s3a.access.key", "minio") \
    .config("spark.hadoop.fs.s3a.secret.key", "minio123") \
    .config("spark.hadoop.fs.s3a.path.style.access", "true") \
    .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem") \
    .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false") \
    .getOrCreate()

spark.sparkContext.setLogLevel("WARN")

print("✅ Spark Session with Delta Lake created successfully.")

# Schema cho dữ liệu từ Kafka
schema = StructType([
    StructField("Time", DoubleType(), True),
    StructField("V1", DoubleType(), True),
    StructField("V2", DoubleType(), True),
    StructField("V3", DoubleType(), True),
    StructField("V4", DoubleType(), True),
    StructField("V5", DoubleType(), True),
    StructField("V6", DoubleType(), True),
    StructField("V7", DoubleType(), True),
    StructField("V8", DoubleType(), True),
    StructField("V9", DoubleType(), True),
    StructField("V10", DoubleType(), True),
    StructField("V11", DoubleType(), True),
    StructField("V12", DoubleType(), True),
    StructField("V13", DoubleType(), True),
    StructField("V14", DoubleType(), True),
    StructField("V15", DoubleType(), True),
    StructField("V16", DoubleType(), True),
    StructField("V17", DoubleType(), True),
    StructField("V18", DoubleType(), True),
    StructField("V19", DoubleType(), True),
    StructField("V20", DoubleType(), True),
    StructField("V21", DoubleType(), True),
    StructField("V22", DoubleType(), True),
    StructField("V23", DoubleType(), True),
    StructField("V24", DoubleType(), True),
    StructField("V25", DoubleType(), True),
    StructField("V26", DoubleType(), True),
    StructField("V27", DoubleType(), True),
    StructField("V28", DoubleType(), True),
    StructField("Amount", DoubleType(), True),
    StructField("Class", DoubleType(), True)
])

# Đọc dữ liệu từ Kafka
kafka_stream_df = spark \
    .readStream \
    .format("kafka") \
    .option("kafka.bootstrap.servers", KAFKA_BROKER) \
    .option("subscribe", KAFKA_TOPIC) \
    .option("startingOffsets", "latest") \
    .load()

# Parse JSON và thêm metadata
transaction_df = kafka_stream_df.selectExpr("CAST(value AS STRING)") \
    .select(from_json(col("value"), schema).alias("data")) \
    .select("data.*") \
    .withColumn("ingestion_time", current_timestamp()) \
    .withColumn("year", year(col("ingestion_time"))) \
    .withColumn("month", month(col("ingestion_time"))) \
    .withColumn("day", dayofmonth(col("ingestion_time")))

# Hàm để ghi vào Bronze layer (Raw data)
def write_to_bronze(df, batch_id):
    print(f"Writing batch {batch_id} to Bronze layer...")
    df.write \
        .format("delta") \
        .mode("append") \
        .option("path", BRONZE_PATH) \
        .partitionBy("year", "month", "day") \
        .save()
    print(f"Batch {batch_id} written to Bronze successfully.")

# Ghi stream vào Bronze layer
bronze_query = transaction_df \
    .writeStream \
    .foreachBatch(write_to_bronze) \
    .outputMode("append") \
    .option("checkpointLocation", "s3a://lakehouse/checkpoints/bronze") \
    .start()

print("Bronze layer streaming started. Writing to MinIO...")
bronze_query.awaitTermination()