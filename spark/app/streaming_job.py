from pyspark.sql import SparkSession
from pyspark.sql.functions import from_json, col, current_timestamp, year, month, dayofmonth
from pyspark.sql.types import StructType, StructField, StringType, DoubleType, IntegerType, LongType, TimestampType

# Cấu hình Kafka
KAFKA_BROKER = "kafka:9092"
# Debezium CDC topic name: <topic.prefix>.<schema>.<table>
KAFKA_TOPIC = "dbserver1.public.transactions"

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

# Schema cho dữ liệu từ Debezium CDC sau khi đã được unwrap (ExtractNewRecordState transform)
# Message format: {"id": 1, "time_seconds": 0.0, "v1": 0.1, ..., "__deleted": "false"}
cdc_value_schema = StructType([
    StructField("id", LongType(), True),
    StructField("time_seconds", DoubleType(), True),
    StructField("v1", DoubleType(), True),
    StructField("v2", DoubleType(), True),
    StructField("v3", DoubleType(), True),
    StructField("v4", DoubleType(), True),
    StructField("v5", DoubleType(), True),
    StructField("v6", DoubleType(), True),
    StructField("v7", DoubleType(), True),
    StructField("v8", DoubleType(), True),
    StructField("v9", DoubleType(), True),
    StructField("v10", DoubleType(), True),
    StructField("v11", DoubleType(), True),
    StructField("v12", DoubleType(), True),
    StructField("v13", DoubleType(), True),
    StructField("v14", DoubleType(), True),
    StructField("v15", DoubleType(), True),
    StructField("v16", DoubleType(), True),
    StructField("v17", DoubleType(), True),
    StructField("v18", DoubleType(), True),
    StructField("v19", DoubleType(), True),
    StructField("v20", DoubleType(), True),
    StructField("v21", DoubleType(), True),
    StructField("v22", DoubleType(), True),
    StructField("v23", DoubleType(), True),
    StructField("v24", DoubleType(), True),
    StructField("v25", DoubleType(), True),
    StructField("v26", DoubleType(), True),
    StructField("v27", DoubleType(), True),
    StructField("v28", DoubleType(), True),
    StructField("amount", DoubleType(), True),
    StructField("class", IntegerType(), True),
    StructField("created_at", LongType(), True),  # Unix timestamp microseconds
    StructField("updated_at", LongType(), True),  # Unix timestamp microseconds
    StructField("__deleted", StringType(), True)  # Debezium delete marker
])

# Đọc dữ liệu từ Kafka
kafka_stream_df = spark \
    .readStream \
    .format("kafka") \
    .option("kafka.bootstrap.servers", KAFKA_BROKER) \
    .option("subscribe", KAFKA_TOPIC) \
    .option("startingOffsets", "earliest") \
    .load()

# Parse JSON từ Debezium CDC (đã unwrap) và filter deleted records
transaction_df = kafka_stream_df.selectExpr("CAST(value AS STRING) as json_value") \
    .select(from_json(col("json_value"), cdc_value_schema).alias("data")) \
    .filter(col("data.__deleted") != "true") \
    .select("data.*") \
    .drop("__deleted") \
    .withColumnRenamed("time_seconds", "Time") \
    .withColumnRenamed("v1", "V1") \
    .withColumnRenamed("v2", "V2") \
    .withColumnRenamed("v3", "V3") \
    .withColumnRenamed("v4", "V4") \
    .withColumnRenamed("v5", "V5") \
    .withColumnRenamed("v6", "V6") \
    .withColumnRenamed("v7", "V7") \
    .withColumnRenamed("v8", "V8") \
    .withColumnRenamed("v9", "V9") \
    .withColumnRenamed("v10", "V10") \
    .withColumnRenamed("v11", "V11") \
    .withColumnRenamed("v12", "V12") \
    .withColumnRenamed("v13", "V13") \
    .withColumnRenamed("v14", "V14") \
    .withColumnRenamed("v15", "V15") \
    .withColumnRenamed("v16", "V16") \
    .withColumnRenamed("v17", "V17") \
    .withColumnRenamed("v18", "V18") \
    .withColumnRenamed("v19", "V19") \
    .withColumnRenamed("v20", "V20") \
    .withColumnRenamed("v21", "V21") \
    .withColumnRenamed("v22", "V22") \
    .withColumnRenamed("v23", "V23") \
    .withColumnRenamed("v24", "V24") \
    .withColumnRenamed("v25", "V25") \
    .withColumnRenamed("v26", "V26") \
    .withColumnRenamed("v27", "V27") \
    .withColumnRenamed("v28", "V28") \
    .withColumnRenamed("amount", "Amount") \
    .withColumnRenamed("class", "Class") \
    .withColumn("ingestion_time", current_timestamp()) \
    .withColumn("year", year(col("ingestion_time"))) \
    .withColumn("month", month(col("ingestion_time"))) \
    .withColumn("day", dayofmonth(col("ingestion_time")))

# Hàm để ghi vào Bronze layer (Raw data)
def write_to_bronze(df, batch_id):
    row_count = df.count()
    if row_count > 0:
        print(f"Writing batch {batch_id} to Bronze layer with {row_count} rows...")
        
        # Repartition để tạo nhiều files nhỏ thay vì 1 file lớn
        # Target: ~10,000-50,000 records per file for optimal performance
        num_partitions = max(1, row_count // 50000)
        
        df.repartition(num_partitions) \
            .write \
            .format("delta") \
            .mode("append") \
            .option("maxRecordsPerFile", 50000) \
            .partitionBy("year", "month", "day") \
            .save(BRONZE_PATH)
        
        print(f"Batch {batch_id} written to Bronze successfully with {num_partitions} partitions.")
    else:
        print(f"Batch {batch_id} is empty, skipping write.")

# Ghi stream vào Bronze layer
bronze_query = transaction_df \
    .writeStream \
    .foreachBatch(write_to_bronze) \
    .outputMode("append") \
    .option("checkpointLocation", "s3a://lakehouse/checkpoints/bronze") \
    .start()

print("Bronze layer streaming started. Writing to MinIO...")
bronze_query.awaitTermination()