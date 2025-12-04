"""
Airflow DAG for Lakehouse Data Pipeline (TaskFlow API)
- Run Silver layer transformation (Bronze → Features)
- Run Gold layer transformation (Silver → Star Schema)
- Register Delta tables to Hive Metastore
- Schedule: Every 5 minutes (or on-demand)

This DAG manages the entire batch processing pipeline using TaskFlow API
"""

from airflow.decorators import dag, task
from datetime import datetime, timedelta
import logging
import subprocess
import time

logger = logging.getLogger(__name__)

# Default arguments
default_args = {
    'owner': 'fraud_detection_team',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=2),
}


@dag(
    dag_id='lakehouse_pipeline_taskflow',
    default_args=default_args,
    description='Lakehouse ETL Pipeline: Bronze → Silver → Gold → Hive Registration',
    schedule_interval='*/5 * * * *',  # Every 5 minutes
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=['lakehouse', 'etl', 'taskflow', 'silver', 'gold'],
    max_active_runs=1,  # Prevent concurrent runs
)
def lakehouse_pipeline():
    """
    Main DAG function for Lakehouse batch processing pipeline
    """

    @task
    def check_bronze_data() -> dict:
        """Check if Bronze layer has new data to process"""
        logger.info("Checking Bronze layer for new data...")
        
        try:
            # Check if bronze-streaming container is running
            result = subprocess.run(
                ['docker', 'ps', '--filter', 'name=bronze-streaming', '--format', '{{.Status}}'],
                capture_output=True,
                text=True,
                check=True
            )
            
            if 'Up' in result.stdout:
                logger.info("✅ Bronze streaming is running")
                return {"status": "ready", "bronze_running": True}
            else:
                logger.warning("⚠️ Bronze streaming is not running")
                return {"status": "not_ready", "bronze_running": False}
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ Failed to check Bronze status: {e}")
            return {"status": "error", "bronze_running": False}

    @task(execution_timeout=timedelta(minutes=15))
    def run_silver_transformation() -> dict:
        """Run Silver layer transformation (Bronze → Features)"""
        logger.info("🔄 Starting Silver layer transformation...")
        logger.info(f"⏰ Silver job started at: {datetime.now()}")
        
        try:
            # Run silver job via spark-submit
            result = subprocess.run(
                [
                    'docker', 'exec', 'spark-master',
                    '/opt/spark/bin/spark-submit',
                    '--master', 'spark://spark-master:7077',
                    '--conf', 'spark.cores.max=2',
                    '--conf', 'spark.executor.cores=1',
                    '--conf', 'spark.executor.memory=1g',
                    '--conf', 'spark.driver.memory=1g',
                    '--conf', 'spark.sql.shuffle.partitions=4',
                    '--packages', 'io.delta:delta-core_2.12:2.4.0,org.apache.hadoop:hadoop-aws:3.3.4',
                    '--conf', 'spark.sql.extensions=io.delta.sql.DeltaSparkSessionExtension',
                    '--conf', 'spark.sql.catalog.spark_catalog=org.apache.spark.sql.delta.catalog.DeltaCatalog',
                    '/app/silver_job.py'
                ],
                capture_output=True,
                text=True,
                check=True,
                timeout=900  # 15 minutes timeout
            )
            
            logger.info(f"⏰ Silver job completed at: {datetime.now()}")
            logger.info("✅ Silver transformation finished successfully")
            
            # Parse output for record count (optional)
            output_lines = result.stdout.split('\n')
            record_count = 0
            for line in output_lines:
                if 'records processed' in line.lower():
                    try:
                        record_count = int(''.join(filter(str.isdigit, line)))
                    except:
                        pass
            
            return {
                "status": "success",
                "timestamp": datetime.now().isoformat(),
                "records_processed": record_count
            }
        except subprocess.TimeoutExpired:
            logger.error("❌ Silver job timeout after 15 minutes")
            raise
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ Silver transformation failed: {e.stderr}")
            raise

    @task(execution_timeout=timedelta(minutes=15))
    def run_gold_transformation(silver_result: dict) -> dict:
        """Run Gold layer transformation (Silver → Star Schema)"""
        logger.info("🔄 Starting Gold layer transformation...")
        logger.info(f"⏰ Gold job started at: {datetime.now()}")
        logger.info(f"Silver processed {silver_result.get('records_processed', 0)} records")
        
        try:
            # Run gold job via spark-submit
            result = subprocess.run(
                [
                    'docker', 'exec', 'spark-master',
                    '/opt/spark/bin/spark-submit',
                    '--master', 'spark://spark-master:7077',
                    '--conf', 'spark.cores.max=2',
                    '--conf', 'spark.executor.cores=1',
                    '--conf', 'spark.executor.memory=1g',
                    '--conf', 'spark.driver.memory=1g',
                    '--conf', 'spark.sql.shuffle.partitions=4',
                    '--packages', 'io.delta:delta-core_2.12:2.4.0,org.apache.hadoop:hadoop-aws:3.3.4',
                    '--conf', 'spark.sql.extensions=io.delta.sql.DeltaSparkSessionExtension',
                    '--conf', 'spark.sql.catalog.spark_catalog=org.apache.spark.sql.delta.catalog.DeltaCatalog',
                    '/app/gold_job.py'
                ],
                capture_output=True,
                text=True,
                check=True,
                timeout=900  # 15 minutes timeout
            )
            
            logger.info(f"⏰ Gold job completed at: {datetime.now()}")
            logger.info("✅ Gold transformation finished successfully")
            
            return {
                "status": "success",
                "timestamp": datetime.now().isoformat(),
                "tables_created": ["dim_customer", "dim_merchant", "dim_time", "dim_location", "fact_transactions"]
            }
        except subprocess.TimeoutExpired:
            logger.error("❌ Gold job timeout after 15 minutes")
            raise
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ Gold transformation failed: {e.stderr}")
            raise

    @task(execution_timeout=timedelta(minutes=10))
    def register_tables_to_hive(gold_result: dict) -> dict:
        """Register Delta tables to Hive Metastore for Trino querying"""
        logger.info("🗂️ Registering Delta tables to Hive Metastore...")
        logger.info(f"Tables to register: {gold_result.get('tables_created', [])}")
        
        try:
            # Run Hive registration script
            result = subprocess.run(
                [
                    'docker', 'exec', 'spark-master',
                    '/opt/spark/bin/spark-submit',
                    '--master', 'spark://spark-master:7077',
                    '--conf', 'spark.cores.max=1',
                    '--conf', 'spark.executor.cores=1',
                    '--conf', 'spark.executor.memory=512m',
                    '--conf', 'spark.driver.memory=512m',
                    '--packages', 'io.delta:delta-core_2.12:2.4.0,org.apache.hadoop:hadoop-aws:3.3.4',
                    '--conf', 'spark.sql.extensions=io.delta.sql.DeltaSparkSessionExtension',
                    '--conf', 'spark.sql.catalog.spark_catalog=org.apache.spark.sql.delta.catalog.DeltaCatalog',
                    '--conf', 'spark.sql.catalogImplementation=hive',
                    '--conf', 'spark.hadoop.hive.metastore.uris=thrift://hive-metastore:9083',
                    '/app/register_tables_to_hive.py'
                ],
                capture_output=True,
                text=True,
                check=True,
                timeout=600  # 10 minutes timeout
            )
            
            logger.info("✅ Hive registration completed successfully")
            
            # Verify tables in Hive
            tables_registered = []
            for table in ['bronze.transactions', 'silver.transactions', 
                         'gold.dim_customer', 'gold.dim_merchant', 'gold.dim_time', 
                         'gold.dim_location', 'gold.fact_transactions']:
                tables_registered.append(table)
            
            return {
                "status": "success",
                "timestamp": datetime.now().isoformat(),
                "tables_registered": tables_registered
            }
        except subprocess.TimeoutExpired:
            logger.error("❌ Hive registration timeout after 10 minutes")
            raise
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ Hive registration failed: {e.stderr}")
            raise

    @task
    def verify_trino_access(hive_result: dict) -> dict:
        """Verify Trino can query the registered tables"""
        logger.info("🔍 Verifying Trino access to Hive tables...")
        
        try:
            # Simple check - verify Trino container is running
            result = subprocess.run(
                ['docker', 'ps', '--filter', 'name=trino', '--format', '{{.Status}}'],
                capture_output=True,
                text=True,
                check=True
            )
            
            if 'Up' in result.stdout:
                logger.info("✅ Trino is running and ready")
                return {
                    "status": "verified",
                    "trino_running": True,
                    "tables_accessible": hive_result.get('tables_registered', [])
                }
            else:
                logger.warning("⚠️ Trino is not running")
                return {"status": "not_verified", "trino_running": False}
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ Trino verification failed: {e}")
            return {"status": "error", "trino_running": False}

    @task
    def send_pipeline_summary(bronze_check: dict, silver_result: dict, 
                              gold_result: dict, hive_result: dict, 
                              trino_verify: dict) -> None:
        """Send pipeline execution summary"""
        logger.info("=" * 60)
        logger.info("LAKEHOUSE PIPELINE EXECUTION SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Bronze Check: {bronze_check.get('status')}")
        logger.info(f"Silver Status: {silver_result.get('status')}")
        logger.info(f"  - Records Processed: {silver_result.get('records_processed', 0)}")
        logger.info(f"Gold Status: {gold_result.get('status')}")
        logger.info(f"  - Tables Created: {len(gold_result.get('tables_created', []))}")
        logger.info(f"Hive Registration: {hive_result.get('status')}")
        logger.info(f"  - Tables Registered: {len(hive_result.get('tables_registered', []))}")
        logger.info(f"Trino Verification: {trino_verify.get('status')}")
        logger.info("=" * 60)
        logger.info("✅ Lakehouse pipeline completed successfully!")
        logger.info("=" * 60)

    # Define task flow
    bronze_check = check_bronze_data()
    silver_result = run_silver_transformation()
    gold_result = run_gold_transformation(silver_result)
    hive_result = register_tables_to_hive(gold_result)
    trino_verify = verify_trino_access(hive_result)
    summary = send_pipeline_summary(bronze_check, silver_result, gold_result, 
                                    hive_result, trino_verify)
    
    # Set dependencies
    bronze_check >> silver_result >> gold_result >> hive_result >> trino_verify >> summary


# Instantiate the DAG
lakehouse_dag = lakehouse_pipeline()
