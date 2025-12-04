-- Test Trino Queries
-- Run: docker exec -it trino trino --server localhost:8081 -f /tmp/test.sql

-- 1. Show catalogs
SHOW CATALOGS;

-- 2. Show Hive schemas
SHOW SCHEMAS FROM hive;

-- 3. Show Hive Gold tables
SHOW TABLES FROM hive.gold;

-- 4. Count fact_transactions via Delta catalog
SELECT COUNT(*) as total_transactions 
FROM delta.default."s3a://lakehouse/gold/fact_transactions";

-- 5. Sample records from fact table
SELECT * 
FROM delta.default."s3a://lakehouse/gold/fact_transactions" 
LIMIT 5;

-- 6. Show Silver tables
SHOW TABLES FROM hive.silver;

-- 7. Count Silver transactions
SELECT COUNT(*) as silver_count
FROM delta.default."s3a://lakehouse/silver/transactions";
