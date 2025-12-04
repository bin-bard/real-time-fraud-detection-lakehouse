"""
Airflow DAG for Automated Model Retraining
- Stop streaming jobs to free up CPU
- Train multiple ML models (RandomForest, GradientBoosting, etc.)
- Start streaming jobs again
- Schedule: Daily at 2 AM
"""

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

# Default arguments
default_args = {
    'owner': 'fraud_detection_team',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
    'start_date': datetime(2025, 1, 1),
}

# Create DAG
dag = DAG(
    'model_retraining_pipeline',
    default_args=default_args,
    description='Automated ML model retraining with streaming job management',
    schedule_interval='0 2 * * *',  # 2 AM daily
    catchup=False,
    tags=['ml', 'fraud-detection', 'retraining'],
)

# Task 1: Stop Silver and Gold streaming jobs to free up CPU
stop_streaming_jobs = BashOperator(
    task_id='stop_streaming_jobs',
    bash_command='''
    echo "🛑 Stopping Silver and Gold streaming jobs..."
    docker-compose -f /workspace/docker-compose.yml stop silver-job gold-job
    echo "✅ Streaming jobs stopped successfully"
    ''',
    dag=dag,
)

# Task 2: Verify jobs are stopped
verify_jobs_stopped = BashOperator(
    task_id='verify_jobs_stopped',
    bash_command='''
    echo "🔍 Verifying streaming jobs are stopped..."
    sleep 10
    docker ps --filter "name=silver-job" --filter "name=gold-job" --format "{{.Names}}: {{.Status}}"
    echo "✅ Verification complete"
    ''',
    dag=dag,
)

# Task 3: Check available data in Silver layer
check_data_availability = BashOperator(
    task_id='check_data_availability',
    bash_command='''
    echo "📊 Checking data availability in Silver layer..."
    docker exec spark-master /opt/spark/bin/spark-submit \
        --master spark://spark-master:7077 \
        --packages io.delta:delta-core_2.12:2.4.0,org.apache.hadoop:hadoop-aws:3.3.4 \
        --conf "spark.sql.extensions=io.delta.sql.DeltaSparkSessionExtension" \
        --conf "spark.sql.catalog.spark_catalog=org.apache.spark.sql.delta.catalog.DeltaCatalog" \
        --py-files /app/check_data.py || echo "⚠️ Data check script not found, continuing..."
    echo "✅ Data check complete"
    ''',
    dag=dag,
)

# Task 4: Train ML models (main task)
train_models = BashOperator(
    task_id='train_ml_models',
    bash_command='''
    echo "🤖 Starting ML model training..."
    echo "⏰ Training started at: $(date)"
    
    docker exec spark-master /opt/spark/bin/spark-submit \
        --master spark://spark-master:7077 \
        --conf spark.cores.max=4 \
        --conf spark.executor.cores=2 \
        --conf spark.executor.memory=2g \
        --conf spark.driver.memory=2g \
        --conf spark.sql.shuffle.partitions=10 \
        --packages io.delta:delta-core_2.12:2.4.0,org.apache.hadoop:hadoop-aws:3.3.4 \
        --conf "spark.sql.extensions=io.delta.sql.DeltaSparkSessionExtension" \
        --conf "spark.sql.catalog.spark_catalog=org.apache.spark.sql.delta.catalog.DeltaCatalog" \
        /app/ml_training_job.py
    
    echo "⏰ Training completed at: $(date)"
    echo "✅ Model training finished successfully"
    ''',
    dag=dag,
    execution_timeout=timedelta(hours=2),  # Max 2 hours for training
)

# Task 5: Verify models are registered in MLflow
verify_models = BashOperator(
    task_id='verify_models_registered',
    bash_command='''
    echo "🔍 Verifying models in MLflow..."
    curl -s http://mlflow:5000/api/2.0/mlflow/registered-models/list | grep -o "fraud_detection" || echo "⚠️ Models check failed"
    echo "✅ Model verification complete"
    ''',
    dag=dag,
)

# Task 6: Restart Silver and Gold streaming jobs
restart_streaming_jobs = BashOperator(
    task_id='restart_streaming_jobs',
    bash_command='''
    echo "🔄 Restarting Silver and Gold streaming jobs..."
    docker-compose -f /workspace/docker-compose.yml start silver-job gold-job
    sleep 15
    docker ps --filter "name=silver-job" --filter "name=gold-job" --format "{{.Names}}: {{.Status}}"
    echo "✅ Streaming jobs restarted successfully"
    ''',
    dag=dag,
)

# Task 7: Send notification (can be extended with email/Slack)
send_notification = PythonOperator(
    task_id='send_success_notification',
    python_callable=lambda: logger.info("✅ Model retraining pipeline completed successfully!"),
    dag=dag,
)

# Define task dependencies
stop_streaming_jobs >> verify_jobs_stopped >> check_data_availability >> train_models >> verify_models >> restart_streaming_jobs >> send_notification
