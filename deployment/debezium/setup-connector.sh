#!/bin/bash

echo "⏳ Waiting for Debezium Connect to be ready..."
until curl -s http://debezium:8083/connectors > /dev/null 2>&1; do
  echo "Debezium not ready yet, retrying in 5 seconds..."
  sleep 5
done

echo "✅ Debezium Connect is ready!"

# Check if connector already exists
CONNECTOR_EXISTS=$(curl -s http://debezium:8083/connectors | grep -c "postgres-connector")

if [ "$CONNECTOR_EXISTS" -gt 0 ]; then
  echo "⚠️  Connector 'postgres-connector' already exists. Skipping creation."
  exit 0
fi

echo "📡 Creating Debezium PostgreSQL connector..."

curl -X POST -H "Content-Type: application/json" \
  --data '{
    "name": "postgres-connector",
    "config": {
      "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
      "tasks.max": "1",
      "database.hostname": "postgres",
      "database.port": "5432",
      "database.user": "postgres",
      "database.password": "postgres",
      "database.dbname": "frauddb",
      "database.server.name": "postgres",
      "table.include.list": "public.transactions",
      "plugin.name": "pgoutput",
      "publication.autocreate.mode": "filtered",
      "topic.prefix": "postgres"
    }
  }' \
  http://debezium:8083/connectors

echo ""
echo "✅ Debezium connector created successfully!"
echo "🔍 Verifying connector status..."

sleep 3
curl -s http://debezium:8083/connectors/postgres-connector/status | jq '.'
