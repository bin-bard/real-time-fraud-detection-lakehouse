"""
Register Delta Lake tables to Hive Metastore

⚠️ LƯU Ý QUAN TRỌNG:
- Hive Metastore chỉ là METADATA CACHE cho Delta catalog
- Query thực tế vẫn đi qua Delta connector (delta.bronze.*, delta.silver.*, delta.gold.*)
- KHÔNG query qua hive catalog (hive.*) - sẽ lỗi "Cannot query Delta Lake table"

Lợi ích:
✅ SHOW TABLES/SCHEMAS nhanh hơn (không scan S3 mỗi lần)
✅ Metabase/DBeaver discover tables nhanh
✅ Tương thích với legacy tools chỉ biết Hive Metastore

Có thể bỏ script này KHÔNG?
- CÓ - Delta connector tự discover tables từ _delta_log/
- NHƯNG: Sẽ chậm hơn khi list tables (phải scan MinIO)
- KHUYẾN NGHỊ: Giữ lại để tối ưu performance
"""

from pyspark.sql import SparkSession
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_spark_session():
    """Khởi tạo Spark Session với Hive Metastore enabled"""
    return SparkSession.builder \
        .appName("RegisterDeltaTablesToHive") \
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
        .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog") \
        .config("spark.hadoop.fs.s3a.endpoint", "http://minio:9000") \
        .config("spark.hadoop.fs.s3a.access.key", "minio") \
        .config("spark.hadoop.fs.s3a.secret.key", "minio123") \
        .config("spark.hadoop.fs.s3a.path.style.access", "true") \
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem") \
        .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false") \
        .config("spark.sql.warehouse.dir", "s3a://lakehouse/warehouse") \
        .config("spark.sql.catalogImplementation", "hive") \
        .config("hive.metastore.uris", "thrift://hive-metastore:9083") \
        .enableHiveSupport() \
        .getOrCreate()

def register_table(spark, database, table_name, delta_path, partition_cols=None):
    """
    Register một Delta Lake table vào Hive Metastore
    
    Args:
        spark: SparkSession
        database: Tên database (vd: 'bronze', 'silver', 'gold')
        table_name: Tên table
        delta_path: S3 path đến Delta Lake table
        partition_cols: List partition columns (optional)
    """
    try:
        # Tạo database nếu chưa tồn tại
        spark.sql(f"CREATE DATABASE IF NOT EXISTS {database}")
        
        # Drop table cũ nếu tồn tại
        spark.sql(f"DROP TABLE IF EXISTS {database}.{table_name}")
        
        # Đọc Delta table để lấy schema
        df = spark.read.format("delta").load(delta_path)
        
        # Tạo external table pointing đến Delta Lake location
        if partition_cols:
            partition_spec = f"PARTITIONED BY ({', '.join(partition_cols)})"
        else:
            partition_spec = ""
        
        # Register as external table
        spark.sql(f"""
            CREATE EXTERNAL TABLE IF NOT EXISTS {database}.{table_name}
            USING DELTA
            LOCATION '{delta_path}'
        """)
        
        # Note: MSCK REPAIR TABLE not supported for Delta v2 tables
        # Delta automatically manages partitions
        
        # Verify
        count = spark.sql(f"SELECT COUNT(*) as cnt FROM {database}.{table_name}").collect()[0]["cnt"]
        logger.info(f"✅ Registered {database}.{table_name} ({count:,} records)")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to register {database}.{table_name}: {str(e)}")
        return False

def main():
    """Register tất cả Delta Lake tables"""
    spark = create_spark_session()
    spark.sparkContext.setLogLevel("WARN")
    
    logger.info("🔧 Starting Delta Lake to Hive Metastore registration...")
    
    # Tables cần register
    tables_config = [
        # Bronze Layer
        {
            "database": "bronze",
            "table_name": "transactions",
            "delta_path": "s3a://lakehouse/bronze/transactions",
            "partition_cols": ["year", "month", "day"]
        },
        
        # Silver Layer
        {
            "database": "silver",
            "table_name": "transactions",
            "delta_path": "s3a://lakehouse/silver/transactions",
            "partition_cols": ["year", "month", "day"]
        },
        
        # Gold Layer - Dimensions
        {
            "database": "gold",
            "table_name": "dim_customer",
            "delta_path": "s3a://lakehouse/gold/dim_customer",
            "partition_cols": None
        },
        {
            "database": "gold",
            "table_name": "dim_merchant",
            "delta_path": "s3a://lakehouse/gold/dim_merchant",
            "partition_cols": None
        },
        {
            "database": "gold",
            "table_name": "dim_time",
            "delta_path": "s3a://lakehouse/gold/dim_time",
            "partition_cols": None
        },
        {
            "database": "gold",
            "table_name": "dim_location",
            "delta_path": "s3a://lakehouse/gold/dim_location",
            "partition_cols": None
        },
        
        # Gold Layer - Fact
        {
            "database": "gold",
            "table_name": "fact_transactions",
            "delta_path": "s3a://lakehouse/gold/fact_transactions",
            "partition_cols": None
        }
    ]
    
    success_count = 0
    fail_count = 0
    
    for config in tables_config:
        logger.info(f"\n📊 Processing {config['database']}.{config['table_name']}...")
        
        # Kiểm tra Delta table tồn tại
        try:
            test_df = spark.read.format("delta").load(config['delta_path'])
            count = test_df.count()
            logger.info(f"   Found {count:,} records in Delta Lake")
            
            # Register vào Hive
            if register_table(
                spark, 
                config['database'], 
                config['table_name'], 
                config['delta_path'],
                config.get('partition_cols')
            ):
                success_count += 1
            else:
                fail_count += 1
                
        except Exception as e:
            logger.warning(f"⚠️  Table not found or empty: {config['delta_path']}")
            logger.warning(f"   Error: {str(e)}")
            logger.warning(f"   (Sẽ được register tự động khi có data)")
            fail_count += 1
    
    # Summary
    logger.info("\n" + "="*60)
    logger.info("📊 Registration Summary:")
    logger.info(f"   ✅ Success: {success_count} tables")
    logger.info(f"   ⚠️  Skipped: {fail_count} tables (chưa có data)")
    logger.info("="*60)
    
    # Show registered tables
    logger.info("\n📚 Registered databases and tables:")
    for db in ["bronze", "silver", "gold"]:
        try:
            tables = spark.sql(f"SHOW TABLES IN {db}").collect()
            if tables:
                logger.info(f"\n{db.upper()} database:")
                for table in tables:
                    logger.info(f"   - {table.tableName}")
        except:
            logger.warning(f"Database {db} not found")
    
    logger.info("\n✅ Registration completed!")
    logger.info("\n⚠️  QUAN TRỌNG: Hive catalog CHỈ LIST được tables, KHÔNG QUERY được!")
    logger.info("   Lý do: Hive connector không hiểu Delta format")
    logger.info("\n🔍 Verify metadata registration (Hive catalog):")
    logger.info("   docker exec -it trino trino --server localhost:8081")
    logger.info("   SHOW CATALOGS;")
    logger.info("   SHOW SCHEMAS FROM hive;")
    logger.info("   SHOW TABLES FROM hive.gold;  ← OK")
    logger.info("   SELECT * FROM hive.gold.fact_transactions;  ← LỖI!")
    logger.info("\n✅ Query data (Delta catalog):")
    logger.info("   SHOW TABLES FROM delta.gold;")
    logger.info("   SELECT * FROM delta.gold.fact_transactions LIMIT 5;  ← ĐÚNG!")
    
    spark.stop()

if __name__ == "__main__":
    main()
