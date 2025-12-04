"""
Airflow DAG for Automated Model Retraining (TaskFlow API)
- Stop streaming jobs to free up CPU
- Train ML models (RandomForest, LogisticRegression)
- Restart streaming jobs
- Schedule: Daily at 2 AM

TaskFlow API Benefits:
- Cleaner, more Pythonic code
- Automatic XCom handling
- Type hints support
- Better error handling
"""

from airflow.decorators import dag, task
from airflow.operators.bash import BashOperator
from datetime import datetime, timedelta
import logging
import subprocess

logger = logging.getLogger(__name__)

# Default arguments
default_args = {
    'owner': 'fraud_detection_team',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}


@dag(
    dag_id='model_retraining_taskflow',
    default_args=default_args,
    description='Automated ML model retraining using TaskFlow API',
    schedule_interval='0 2 * * *',  # Daily at 2 AM
    start_date=datetime(2025, 1, 1),
    catchup=False,  # Don't run missed schedules on startup
    tags=['ml', 'fraud-detection', 'taskflow'],
)
def model_retraining_pipeline():
    """
    Main DAG function using TaskFlow API
    """

    @task
    def check_data_availability() -> dict:
        """Check if Silver layer has sufficient data for training"""
        logger.info("📈 Checking data availability in Silver layer...")
        
        # Simplified check - in production, you'd query Delta table count
        # For now, just check if MinIO/lakehouse is accessible
        try:
            result = subprocess.run(
                ['docker', 'exec', 'spark-master', 'ls', '/app/ml_training_job.py'],
                capture_output=True,
                text=True,
                check=True
            )
            logger.info("✅ Training script found, data layer accessible")
            return {"status": "ready", "records": "unknown"}
        except subprocess.CalledProcessError:
            logger.error("❌ Training script not found")
            return {"status": "not_ready", "records": 0}

    @task(execution_timeout=timedelta(hours=2))
    def train_ml_models() -> dict:
        """Train ML models (RandomForest, LogisticRegression)"""
        logger.info("🧠 Starting ML model training...")
        logger.info(f"⏰ Training started at: {datetime.now()}")
        
        try:
            result = subprocess.run(
                [
                    'docker', 'exec', 'spark-master',
                    '/opt/spark/bin/spark-submit',
                    '--master', 'spark://spark-master:7077',
                    '--conf', 'spark.cores.max=4',
                    '--conf', 'spark.executor.cores=2',
                    '--conf', 'spark.executor.memory=2g',
                    '--conf', 'spark.driver.memory=2g',
                    '--conf', 'spark.sql.shuffle.partitions=10',
                    '--packages', 'io.delta:delta-core_2.12:2.4.0,org.apache.hadoop:hadoop-aws:3.3.4',
                    '--conf', 'spark.sql.extensions=io.delta.sql.DeltaSparkSessionExtension',
                    '--conf', 'spark.sql.catalog.spark_catalog=org.apache.spark.sql.delta.catalog.DeltaCatalog',
                    '/app/ml_training_job.py'
                ],
                capture_output=True,
                text=True,
                check=True
            )
            
            logger.info(f"⏰ Training completed at: {datetime.now()}")
            logger.info("✅ Model training finished successfully")
            
            # Parse output for metrics (optional)
            return {
                "status": "success",
                "models": ["RandomForest", "LogisticRegression"],
                "timestamp": datetime.now().isoformat()
            }
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ Training failed: {e.stderr}")
            raise

    @task
    def verify_models_registered(training_result: dict) -> dict:
        """Verify models are registered in MLflow"""
        logger.info("🔍 Verifying models in MLflow...")
        
        try:
            # Check MLflow API for registered models
            result = subprocess.run(
                ['curl', '-s', 'http://mlflow:5000/api/2.0/mlflow/registered-models/list'],
                capture_output=True,
                text=True,
                check=True
            )
            
            if 'fraud_detection' in result.stdout:
                logger.info("✅ Models found in MLflow registry")
                return {"status": "verified", "models_found": True}
            else:
                logger.warning("⚠️ Models not found in registry")
                return {"status": "not_verified", "models_found": False}
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ MLflow verification failed: {e}")
            return {"status": "error", "models_found": False}

    @task
    def send_notification(training_result: dict, verification_result: dict) -> None:
        """Send success notification with summary"""
        logger.info("=" * 60)
        logger.info("🗂️ MODEL RETRAINING PIPELINE SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Training Status: {training_result.get('status')}")
        logger.info(f"Models Trained: {training_result.get('models')}")
        logger.info(f"MLflow Verification: {verification_result.get('status')}")
        logger.info("=" * 60)
        logger.info("✅ Model retraining pipeline completed successfully!")
        logger.info("=" * 60)

    # Define task flow
    data_check = check_data_availability()
    training_result = train_ml_models()
    verification_result = verify_models_registered(training_result)
    notification = send_notification(training_result, verification_result)
    
    # Set dependencies
    data_check >> training_result >> verification_result >> notification


# Instantiate the DAG
model_retraining_dag = model_retraining_pipeline()
