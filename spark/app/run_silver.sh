#!/bin/bash

echo "🔄 Starting Silver batch processing loop..."
sleep 90

while true; do
    echo "📊 Running Silver batch job at $(date)"
    
    /opt/spark/bin/spark-submit \
        --master spark://spark-master:7077 \
        --conf spark.cores.max=1 \
        --conf spark.executor.cores=1 \
        --conf spark.executor.memory=512m \
        --conf spark.driver.memory=512m \
        --conf spark.sql.shuffle.partitions=2 \
        --conf "spark.sql.extensions=io.delta.sql.DeltaSparkSessionExtension" \
        --conf "spark.sql.catalog.spark_catalog=org.apache.spark.sql.delta.catalog.DeltaCatalog" \
        --packages io.delta:delta-core_2.12:2.4.0,org.apache.hadoop:hadoop-aws:3.3.4 \
        /app/silver_job.py
    
    echo "✅ Silver batch completed. Sleeping 5 minutes..."
    sleep 300
done
