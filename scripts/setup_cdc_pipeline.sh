#!/bin/bash

# Wait for Kafka Connect to be ready
echo "Waiting for Kafka Connect to be ready..."
until curl -s -o /dev/null -w "%{http_code}" http://localhost:8083/ | grep -q "200"; do
    echo "Kafka Connect is not ready yet. Waiting..."
    sleep 5
done

echo "Kafka Connect is ready!"

# Register the Debezium PostgreSQL connector
echo "Registering Debezium PostgreSQL connector..."
curl -i -X POST -H "Accept:application/json" -H "Content-Type:application/json" \
  http://localhost:8083/connectors/ \
  -d @config/debezium/register-postgres-connector.json

echo ""
echo "Connector registration complete!"

# Check connector status
echo "Checking connector status..."
sleep 5
curl -s http://localhost:8083/connectors/postgres-transactions-connector/status | jq '.'

echo ""
echo "Setup complete! CDC pipeline is now active."
echo "Topic name: dbserver1.public.transactions"
