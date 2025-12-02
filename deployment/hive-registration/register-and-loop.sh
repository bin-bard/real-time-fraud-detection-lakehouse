#!/bin/bash
# ============================================================
# Auto-register Delta tables to Hive Metastore
# Chạy tự động khi start docker-compose, loop mỗi 1 giờ
# ============================================================

echo "========================================="
echo "🔧 Hive Metastore Registration Service"
echo "========================================="

# Wait for Hive Metastore to be ready (check port 9083)
echo ""
echo "⏳ Waiting for Hive Metastore to be ready..."
MAX_METASTORE_WAIT=30  # 30 attempts * 5s = 2.5 minutes
METASTORE_ATTEMPT=0

while [ $METASTORE_ATTEMPT -lt $MAX_METASTORE_WAIT ]; do
    if nc -z hive-metastore 9083 2>/dev/null; then
        echo "✅ Hive Metastore is ready!"
        break
    fi
    echo "   Attempt $((METASTORE_ATTEMPT + 1))/$MAX_METASTORE_WAIT - Waiting for Hive Metastore..."
    sleep 5
    METASTORE_ATTEMPT=$((METASTORE_ATTEMPT + 1))
done

if [ $METASTORE_ATTEMPT -ge $MAX_METASTORE_WAIT ]; then
    echo "❌ Hive Metastore failed to start after 2.5 minutes!"
    exit 1
fi

# Wait for Gold job to have data (check every 30s for 10 minutes)
echo ""
echo "⏳ Waiting for Gold layer to have data..."
MAX_WAIT=20  # 20 attempts * 30s = 10 minutes
ATTEMPT=0

while [ $ATTEMPT -lt $MAX_WAIT ]; do
    # Check if Gold fact table exists and has data
    GOLD_CHECK=$(ls /tmp 2>&1)  # Dummy check, will be replaced by actual check
    
    # Try to check MinIO for gold data (simplified check)
    echo "   Attempt $((ATTEMPT + 1))/$MAX_WAIT - Waiting for Gold tables..."
    sleep 30
    ATTEMPT=$((ATTEMPT + 1))
    
    # After 3 minutes, try to register anyway
    if [ $ATTEMPT -ge 6 ]; then
        echo "   ⚠️  Proceeding with registration (Gold may have data now)..."
        break
    fi
done

# Function to run registration
run_registration() {
    echo ""
    echo "🚀 Running Delta to Hive registration..."
    echo "========================================="
    
    /opt/spark/bin/spark-submit \
        --master spark://spark-master:7077 \
        --conf spark.cores.max=1 \
        --conf spark.executor.cores=1 \
        --conf spark.executor.memory=512m \
        --conf spark.driver.memory=512m \
        --packages io.delta:delta-core_2.12:2.4.0,org.apache.hadoop:hadoop-aws:3.3.4 \
        /app/register_tables_to_hive.py
    
    if [ $? -eq 0 ]; then
        echo "✅ Registration completed successfully!"
        return 0
    else
        echo "❌ Registration failed!"
        return 1
    fi
}

# First registration attempt
echo ""
echo "📊 First registration attempt..."
run_registration

# Loop: Re-register every 1 hour to catch new tables
echo ""
echo "♻️  Entering maintenance loop (re-register every 1 hour)..."
echo "   (This keeps Hive Metastore in sync with Delta Lake)"

while true; do
    echo ""
    echo "⏰ $(date '+%Y-%m-%d %H:%M:%S') - Next registration in 1 hour..."
    sleep 3600  # 1 hour
    
    echo ""
    echo "🔄 Running scheduled registration..."
    run_registration
done
