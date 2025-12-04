#!/bin/bash
set -e

# Wait for PostgreSQL to be ready
echo "⏳ Waiting for metastore-db to be ready..."
MAX_RETRIES=30
RETRY_COUNT=0

until pg_isready -h metastore-db -p 5432 -U hive > /dev/null 2>&1; do
  RETRY_COUNT=$((RETRY_COUNT + 1))
  if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
    echo "❌ Failed to connect to metastore-db after $MAX_RETRIES attempts"
    exit 1
  fi
  echo "Waiting for metastore-db... (attempt $RETRY_COUNT/$MAX_RETRIES)"
  sleep 2
done
echo "✅ metastore-db is ready!"

# Setup Hadoop client options for Metastore
export HADOOP_CLIENT_OPTS="${HADOOP_CLIENT_OPTS} -Xmx1G -Djavax.jdo.option.ConnectionDriverName=org.postgresql.Driver -Djavax.jdo.option.ConnectionURL=jdbc:postgresql://metastore-db:5432/metastore -Djavax.jdo.option.ConnectionUserName=hive -Djavax.jdo.option.ConnectionPassword=hive"

# Check if schema already exists by querying the table directly
echo "🔍 Checking if Hive Metastore schema exists..."
SCHEMA_CHECK=$(PGPASSWORD=hive psql -h metastore-db -U hive -d metastore -t -A -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'BUCKETING_COLS';" 2>/dev/null || echo "0")

if [ "$SCHEMA_CHECK" = "1" ]; then
    echo "✅ Hive Metastore schema already exists (found BUCKETING_COLS table), skipping initialization"
else
    echo "🔧 Initializing Hive Metastore schema..."
    /opt/hive/bin/schematool -dbType postgres -initSchema
    
    if [ $? -eq 0 ]; then
        echo "✅ Hive Metastore schema initialized successfully"
    else
        echo "❌ Schema initialization failed! Check if schema already partially exists."
        echo "💡 If you see 'relation already exists' errors, the schema is already initialized."
        echo "💡 To force re-initialization, run: docker compose down -v"
        exit 1
    fi
fi

echo "🚀 Starting Hive Metastore service..."
exec /opt/hive/bin/hive --service metastore

