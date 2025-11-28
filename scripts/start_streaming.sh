#!/bin/bash

# Script để start Spark streaming job
echo "Starting Spark streaming job..."

# Kill existing job if any
docker exec spark-master pkill -9 -f "streaming_job.py" 2>/dev/null || true

# Wait a bit
sleep 2

# Submit new job
docker exec spark-master bash -c "nohup /opt/spark/bin/spark-submit \
  --master spark://spark-master:7077 \
  --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0,io.delta:delta-core_2.12:2.4.0,org.apache.hadoop:hadoop-aws:3.3.4 \
  /app/streaming_job.py > /tmp/streaming.log 2>&1 &"

echo "Job submitted. Waiting for initialization..."
sleep 5

echo "Recent logs:"
docker exec spark-master tail -30 /tmp/streaming.log

echo ""
echo "To monitor logs: docker exec spark-master tail -f /tmp/streaming.log"
