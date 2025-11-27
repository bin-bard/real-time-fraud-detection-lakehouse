#!/bin/bash

# Script để cấu hình Debezium PostgreSQL connector
# Chạy sau khi tất cả services đã start

echo "🔧 Setting up Debezium PostgreSQL Connector..."

# Wait for Debezium Connect to be ready
echo "⏳ Waiting for Debezium Connect to start..."
sleep 30

# Register PostgreSQL connector
curl -X POST http://localhost:8083/connectors \
  -H "Content-Type: application/json" \
  -d '{
    "name": "postgres-fraud-connector",
    "config": {
      "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
      "database.hostname": "postgres",
      "database.port": "5432",
      "database.user": "postgres",
      "database.password": "postgres",
      "database.dbname": "frauddb",
      "database.server.name": "postgres",
      "table.include.list": "public.transactions",
      "plugin.name": "pgoutput",
      "publication.autocreate.mode": "filtered",
      "topic.prefix": "postgres",
      "transforms": "unwrap",
      "transforms.unwrap.type": "io.debezium.transforms.ExtractNewRecordState",
      "transforms.unwrap.drop.tombstones": "false",
      "key.converter": "org.apache.kafka.connect.json.JsonConverter",
      "value.converter": "org.apache.kafka.connect.json.JsonConverter",
      "key.converter.schemas.enable": "false",
      "value.converter.schemas.enable": "false"
    }
  }'

echo ""
echo "✅ Debezium connector registered!"
echo ""
echo "📊 Check connector status:"
echo "   curl http://localhost:8083/connectors/postgres-fraud-connector/status"
echo ""
echo "📋 List all connectors:"
echo "   curl http://localhost:8083/connectors"
echo ""
echo "🎯 Kafka topic created:"
echo "   postgres.public.transactions"
echo ""
