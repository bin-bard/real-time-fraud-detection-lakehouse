from pyspark.sql import SparkSession
from pyspark.sql.functions import from_json, col, current_timestamp, year, month, dayofmonth, to_timestamp, get_json_object
from pyspark.sql.types import StructType, StructField, StringType, DoubleType

# Cấu hình Kafka - Đọc CDC events từ Debezium
KAFKA_BROKER = "kafka:9092"
KAFKA_TOPIC = "postgres.public.transactions"  # Debezium topic pattern

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

# Schema cho dữ liệu Sparkov từ Debezium CDC
# Debezium gửi dạng: {"payload": {"after": {...}}}
schema = StructType([
    StructField("trans_date_trans_time", StringType(), True),
    StructField("cc_num", StringType(), True),  # Long as String to avoid overflow
    StructField("merchant", StringType(), True),
    StructField("category", StringType(), True),
    StructField("amt", DoubleType(), True),
    StructField("first", StringType(), True),
    StructField("last", StringType(), True),
    StructField("gender", StringType(), True),
    StructField("street", StringType(), True),
    StructField("city", StringType(), True),
    StructField("state", StringType(), True),
    StructField("zip", StringType(), True),
    StructField("lat", DoubleType(), True),
    StructField("long", DoubleType(), True),
    StructField("city_pop", StringType(), True),
    StructField("job", StringType(), True),
    StructField("dob", StringType(), True),
    StructField("trans_num", StringType(), True),
    StructField("unix_time", StringType(), True),
    StructField("merch_lat", DoubleType(), True),
    StructField("merch_long", DoubleType(), True),
    StructField("is_fraud", StringType(), True)
])

# Đọc dữ liệu từ Kafka (Debezium CDC format)
kafka_stream_df = spark \
    .readStream \
    .format("kafka") \
    .option("kafka.bootstrap.servers", KAFKA_BROKER) \
    .option("subscribe", KAFKA_TOPIC) \
    .option("startingOffsets", "latest") \
    .load()

# Parse Debezium JSON format: {"payload": {"after": {...data...}}}
# Extract the "after" field which contains the actual transaction data
transaction_df = kafka_stream_df.selectExpr("CAST(value AS STRING) as json_string") \
    .select(get_json_object(col("json_string"), "$.payload.after").alias("payload")) \
    .select(from_json(col("payload"), schema).alias("data")) \
    .select("data.*") \
    .withColumn("trans_timestamp", to_timestamp(col("trans_date_trans_time"), "yyyy-MM-dd HH:mm:ss")) \
    .withColumn("ingestion_time", current_timestamp()) \
    .withColumn("year", year(col("trans_timestamp"))) \
    .withColumn("month", month(col("trans_timestamp"))) \
    .withColumn("day", dayofmonth(col("trans_timestamp")))

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