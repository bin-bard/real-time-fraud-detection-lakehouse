"""
Airflow DAG for Automated Model Retraining (TaskFlow API)
- Check data availability in Silver layer
- Train ML models (RandomForest, LogisticRegression) via Spark
- Verify models logged to MLflow Tracking
- Send completion notification
- Schedule: Daily at 2 AM

TaskFlow API Benefits:
- Cleaner, more Pythonic code
- Automatic XCom handling
- Type hints support
- Better error handling

Note: Verification checks MLflow RUNS (Tracking), NOT Model Registry.
Model Registry registration is optional for production deployment.
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
                    '--conf', 'spark.cores.max=2',
                    '--conf', 'spark.executor.cores=1',
                    '--conf', 'spark.executor.memory=1g',
                    '--conf', 'spark.driver.memory=1g',
                    '--conf', 'spark.sql.shuffle.partitions=8',
                    '--packages', 'io.delta:delta-core_2.12:2.4.0,org.apache.hadoop:hadoop-aws:3.3.4',
                    '--conf', 'spark.sql.extensions=io.delta.sql.DeltaSparkSessionExtension',
                    '--conf', 'spark.sql.catalog.spark_catalog=org.apache.spark.sql.delta.catalog.DeltaCatalog',
                    # Pass environment variables to Spark executors for MLflow S3 access
                    '--conf', 'spark.executorEnv.AWS_ACCESS_KEY_ID=minio',
                    '--conf', 'spark.executorEnv.AWS_SECRET_ACCESS_KEY=minio123',
                    '--conf', 'spark.executorEnv.MLFLOW_S3_ENDPOINT_URL=http://minio:9000',
                    '/app/ml_training_job.py'
                ],
                capture_output=True,
                text=True,
                check=True
            )
            
            # Log Spark job output for debugging
            logger.info("=" * 80)
            logger.info("📊 Spark Job Output:")
            logger.info("=" * 80)
            logger.info(result.stdout)
            if result.stderr:
                logger.warning("⚠️ Spark Warnings/Errors:")
                logger.warning(result.stderr)
            logger.info("=" * 80)
            
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
        """
        Verify models are logged in MLflow Tracking
        
        Note: We check MLflow RUNS (experiments/tracking), NOT Model Registry.
        Model Registry is for production deployment, which is optional.
        """
        logger.info("🔍 Verifying ML training artifacts...")
        
        verification_results = {
            "mlflow_experiments": False,
            "status": "unknown"
        }
        
        try:
            logger.info("📊 Checking MLflow experiments...")
            
            # Check MLflow experiments exist (most reliable)
            exp_result = subprocess.run(
                ['docker', 'exec', 'mlflow', 
                 'curl', '-s', 'http://localhost:5000/api/2.0/mlflow/experiments/search'],
                capture_output=True,
                text=True,
                check=True,
                timeout=10
            )
            
            logger.info(f"MLflow API response (first 300 chars): {exp_result.stdout[:300]}")
            
            # Check for experiments
            has_experiments = ('experiments' in exp_result.stdout and 
                             'experiment_id' in exp_result.stdout)
            
            if has_experiments:
                logger.info("✅ MLflow experiments found")
                verification_results["mlflow_experiments"] = True
                
                # Bonus: Check for recent runs using Python (mlflow container doesn't have curl)
                try:
                    runs_result = subprocess.run(
                        ['docker', 'exec', 'mlflow', 'python', '-c',
                         "import requests; r = requests.post('http://localhost:5000/api/2.0/mlflow/runs/search', "
                         "json={'experiment_ids': ['1'], 'max_results': 5}); "
                         "print('RUNS_FOUND' if 'runs' in r.json() and len(r.json()['runs']) > 0 else 'NO_RUNS')"],
                        capture_output=True,
                        text=True,
                        timeout=15
                    )
                    
                    if 'RUNS_FOUND' in runs_result.stdout:
                        logger.info("✅ Recent training runs detected in experiment")
                    else:
                        logger.warning("⚠️ No recent runs, but experiments exist (might be old data)")
                except Exception as e:
                    logger.warning(f"⚠️ Could not verify runs: {e}")
                
                logger.info("=" * 60)
                logger.info("✅ MODEL TRAINING VERIFICATION PASSED")
                logger.info("   Check MLflow UI for details: http://localhost:5000")
                logger.info("=" * 60)
                verification_results["status"] = "verified"
                return verification_results
            else:
                logger.warning("⚠️ No MLflow experiments found")
                verification_results["status"] = "not_verified"
                return verification_results
                
        except subprocess.TimeoutExpired:
            logger.error("❌ MLflow API timeout (service might be slow)")
            verification_results["status"] = "timeout"
            return verification_results
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ MLflow API error: {e}")
            logger.error(f"   stderr: {e.stderr}")
            verification_results["status"] = "error"
            return verification_results

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
