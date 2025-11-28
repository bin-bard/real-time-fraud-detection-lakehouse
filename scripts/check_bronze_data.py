from pyspark.sql import SparkSession
from delta import *

# Initialize Spark Session with Delta Lake
spark = SparkSession.builder \
    .appName("CheckBronzeData") \
    .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
    .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog") \
    .config("spark.hadoop.fs.s3a.endpoint", "http://minio:9000") \
    .config("spark.hadoop.fs.s3a.access.key", "minio") \
    .config("spark.hadoop.fs.s3a.secret.key", "minio123") \
    .config("spark.hadoop.fs.s3a.path.style.access", "true") \
    .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem") \
    .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false") \
    .getOrCreate()

# Read Bronze Delta table
bronze_df = spark.read.format("delta").load("s3a://lakehouse/bronze/transactions")

# Show statistics
print(f"\n📊 BRONZE LAYER STATISTICS")
print(f"{'='*50}")
print(f"Total records: {bronze_df.count()}")
print(f"\nSchema:")
bronze_df.printSchema()
print(f"\nSample data (first 5 rows):")
bronze_df.show(5, truncate=False)

# Check partitions
print(f"\n📁 PARTITIONS:")
spark.sql("SELECT year, month, day, COUNT(*) as count FROM delta.`s3a://lakehouse/bronze/transactions` GROUP BY year, month, day").show()

# Fraud detection stats
print(f"\n🚨 FRAUD STATISTICS:")
bronze_df.groupBy("Class").count().show()

spark.stop()
