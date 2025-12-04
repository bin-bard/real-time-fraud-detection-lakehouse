-- ============================================================
-- GOLD LAYER VIEWS for DELTA CATALOG
-- Tạo views trong Delta catalog để Trino, Metabase, Chatbot query
-- Catalog: delta (KHÔNG phải hive - Hive connector không đọc được Delta format!)
-- Schema: gold
-- ============================================================

-- ⚠️ QUAN TRỌNG:
-- - Delta Lake tables được query qua DELTA CATALOG (delta.gold.*)
-- - KHÔNG dùng Hive catalog (hive.gold.*) - sẽ lỗi "Cannot query Delta Lake table"
-- - Hive Metastore chỉ là metadata store, không thực sự query được Delta format
-- - Metabase/Chatbot/DBeaver phải kết nối: jdbc:trino://localhost:8085/delta

-- ============================================================
-- 1. DAILY SUMMARY VIEW
-- Tổng hợp metrics theo ngày cho Dashboard
-- ============================================================
CREATE OR REPLACE VIEW delta.gold.daily_summary AS
SELECT 
    YEAR(transaction_timestamp) as year,
    MONTH(transaction_timestamp) as month,
    DAY(transaction_timestamp) as day,
    DATE(transaction_timestamp) as report_date,
    
    -- Transaction counts
    COUNT(*) as total_transactions,
    SUM(CASE WHEN is_fraud = 1 THEN 1 ELSE 0 END) as fraud_transactions,
    SUM(CASE WHEN is_fraud = 0 THEN 1 ELSE 0 END) as normal_transactions,
    
    -- Amount metrics
    AVG(transaction_amount) as avg_transaction_amount,
    MAX(transaction_amount) as max_transaction_amount,
    MIN(transaction_amount) as min_transaction_amount,
    SUM(transaction_amount) as total_amount,
    SUM(CASE WHEN is_fraud = 1 THEN transaction_amount ELSE 0 END) as fraud_amount,
    
    -- Distance metrics (null-safe)
    AVG(CASE WHEN distance_km >= 0 THEN distance_km END) as avg_distance,
    MAX(CASE WHEN distance_km >= 0 THEN distance_km END) as max_distance,
    
    -- Fraud rate
    CAST(SUM(CASE WHEN is_fraud = 1 THEN 1 ELSE 0 END) AS DOUBLE) / COUNT(*) as fraud_rate,
    
    -- Average fraud amount
    CASE 
        WHEN SUM(CASE WHEN is_fraud = 1 THEN 1 ELSE 0 END) > 0 
        THEN SUM(CASE WHEN is_fraud = 1 THEN transaction_amount ELSE 0 END) / 
             SUM(CASE WHEN is_fraud = 1 THEN 1 ELSE 0 END)
        ELSE 0 
    END as avg_fraud_amount
    
FROM delta.gold.fact_transactions
GROUP BY 
    YEAR(transaction_timestamp),
    MONTH(transaction_timestamp),
    DAY(transaction_timestamp),
    DATE(transaction_timestamp);


-- ============================================================
-- 2. HOURLY SUMMARY VIEW
-- Phân tích patterns theo giờ
-- ============================================================
CREATE OR REPLACE VIEW delta.gold.hourly_summary AS
SELECT 
    YEAR(transaction_timestamp) as year,
    MONTH(transaction_timestamp) as month,
    DAY(transaction_timestamp) as day,
    transaction_hour as hour,
    
    COUNT(*) as total_transactions,
    SUM(CASE WHEN is_fraud = 1 THEN 1 ELSE 0 END) as fraud_transactions,
    AVG(transaction_amount) as avg_amount,
    AVG(CASE WHEN distance_km >= 0 THEN distance_km END) as avg_distance,
    
    CAST(SUM(CASE WHEN is_fraud = 1 THEN 1 ELSE 0 END) AS DOUBLE) / COUNT(*) as fraud_rate
    
FROM delta.gold.fact_transactions
GROUP BY 
    YEAR(transaction_timestamp),
    MONTH(transaction_timestamp),
    DAY(transaction_timestamp),
    transaction_hour;


-- ============================================================
-- 3. STATE SUMMARY VIEW
-- Phân tích theo bang (geographic)
-- ============================================================
CREATE OR REPLACE VIEW delta.gold.state_summary AS
SELECT 
    c.customer_state as state,
    
    COUNT(*) as total_transactions,
    SUM(CASE WHEN f.is_fraud = 1 THEN 1 ELSE 0 END) as fraud_transactions,
    AVG(f.transaction_amount) as avg_amount,
    AVG(CASE WHEN f.distance_km >= 0 THEN f.distance_km END) as avg_distance,
    
    CAST(SUM(CASE WHEN f.is_fraud = 1 THEN 1 ELSE 0 END) AS DOUBLE) / COUNT(*) as fraud_rate
    
FROM delta.gold.fact_transactions f
JOIN delta.gold.dim_customer c 
    ON f.customer_key = c.customer_key
GROUP BY c.customer_state
ORDER BY fraud_transactions DESC;


-- ============================================================
-- 4. CATEGORY SUMMARY VIEW
-- Phán tích theo category
-- ============================================================
CREATE OR REPLACE VIEW delta.gold.category_summary AS
SELECT 
    transaction_category as category,
    
    COUNT(*) as total_transactions,
    SUM(CASE WHEN is_fraud = 1 THEN 1 ELSE 0 END) as fraud_transactions,
    AVG(transaction_amount) as avg_amount,
    
    CAST(SUM(CASE WHEN is_fraud = 1 THEN 1 ELSE 0 END) AS DOUBLE) / COUNT(*) as fraud_rate
    
FROM delta.gold.fact_transactions
GROUP BY transaction_category
ORDER BY fraud_rate DESC;


-- ============================================================
-- 5. AMOUNT RANGE SUMMARY VIEW
-- Phân tích theo khoảng tiền
-- ============================================================
CREATE OR REPLACE VIEW delta.gold.amount_summary AS
SELECT 
    amount_bin as amount_range,
    
    COUNT(*) as total_transactions,
    SUM(CASE WHEN is_fraud = 1 THEN 1 ELSE 0 END) as fraud_transactions,
    AVG(transaction_amount) as avg_amount,
    
    CAST(SUM(CASE WHEN is_fraud = 1 THEN 1 ELSE 0 END) AS DOUBLE) / COUNT(*) as fraud_rate
    
FROM delta.gold.fact_transactions
GROUP BY amount_bin
ORDER BY fraud_rate DESC;


-- ============================================================
-- 6. LATEST METRICS VIEW
-- Real-time metrics cho monitoring dashboard
-- ============================================================
CREATE OR REPLACE VIEW delta.gold.latest_metrics AS
SELECT 
    -- Today's metrics
    COUNT(*) as total_transactions_today,
    SUM(CASE WHEN is_fraud = 1 THEN 1 ELSE 0 END) as fraud_detected_today,
    AVG(transaction_amount) as avg_amount_today,
    AVG(CASE WHEN distance_km >= 0 THEN distance_km END) as avg_distance_today,
    MAX(transaction_timestamp) as last_update,
    
    -- Fraud rate
    CAST(SUM(CASE WHEN is_fraud = 1 THEN 1 ELSE 0 END) AS DOUBLE) / COUNT(*) as fraud_rate_today,
    
    -- Alert level
    CASE 
        WHEN CAST(SUM(CASE WHEN is_fraud = 1 THEN 1 ELSE 0 END) AS DOUBLE) / COUNT(*) > 0.01 THEN 'HIGH'
        WHEN CAST(SUM(CASE WHEN is_fraud = 1 THEN 1 ELSE 0 END) AS DOUBLE) / COUNT(*) > 0.005 THEN 'MEDIUM'
        ELSE 'LOW'
    END as alert_level
    
FROM delta.gold.fact_transactions
WHERE DATE(transaction_timestamp) = CURRENT_DATE;


-- ============================================================
-- 7. FRAUD PATTERNS VIEW
-- Top fraud patterns theo amount range
-- ============================================================
CREATE OR REPLACE VIEW delta.gold.fraud_patterns AS
SELECT 
    amount_bin as amount_range,
    
    COUNT(*) as fraud_count,
    AVG(transaction_amount) as avg_fraud_amount,
    AVG(CASE WHEN distance_km >= 0 THEN distance_km END) as avg_fraud_distance,
    
    -- Time patterns
    AVG(transaction_hour) as avg_hour,
    SUM(CASE WHEN is_weekend_transaction = 1 THEN 1 ELSE 0 END) as weekend_frauds
    
FROM delta.gold.fact_transactions
WHERE is_fraud = 1
GROUP BY amount_bin
ORDER BY fraud_count DESC;


-- ============================================================
-- 8. MERCHANT ANALYSIS VIEW
-- Top merchants by fraud activity
-- ============================================================
CREATE OR REPLACE VIEW delta.gold.merchant_analysis AS
SELECT 
    f.merchant,
    f.transaction_category as merchant_category,
    
    COUNT(*) as total_transactions,
    SUM(CASE WHEN f.is_fraud = 1 THEN 1 ELSE 0 END) as fraud_transactions,
    AVG(f.transaction_amount) as avg_amount,
    
    CAST(SUM(CASE WHEN f.is_fraud = 1 THEN 1 ELSE 0 END) AS DOUBLE) / COUNT(*) as fraud_rate
    
FROM delta.gold.fact_transactions f
GROUP BY f.merchant, f.transaction_category
HAVING COUNT(*) > 10  -- Filter out low-volume merchants
ORDER BY fraud_rate DESC
LIMIT 100;


-- ============================================================
-- 9. TIME PERIOD ANALYSIS VIEW
-- Phân tích theo time period (Morning, Afternoon, Evening, Night)
-- ============================================================
CREATE OR REPLACE VIEW delta.gold.time_period_analysis AS
SELECT 
    t.time_period,
    t.is_weekend,
    
    COUNT(*) as total_transactions,
    SUM(CASE WHEN f.is_fraud = 1 THEN 1 ELSE 0 END) as fraud_transactions,
    AVG(f.transaction_amount) as avg_amount,
    
    CAST(SUM(CASE WHEN f.is_fraud = 1 THEN 1 ELSE 0 END) AS DOUBLE) / COUNT(*) as fraud_rate
    
FROM delta.gold.fact_transactions f
JOIN delta.gold.dim_time t 
    ON f.time_key = t.time_key
GROUP BY t.time_period, t.is_weekend
ORDER BY fraud_rate DESC;


-- ============================================================
-- CÁCH TẠO VIEWS (Execute từ Trino CLI)
-- ============================================================

-- Step 1: Connect to Trino
-- docker exec -it trino trino --server localhost:8081

-- Step 2: Execute file này
-- Copy-paste từng CREATE VIEW statement vào Trino CLI

-- Step 3: Verify
-- SHOW TABLES FROM delta.gold;
-- (Sẽ thấy 5 base tables + 9 views)


-- ============================================================
-- USAGE EXAMPLES - CHO METABASE/CHATBOT
-- ============================================================

-- ⚠️ LƯU Ý: Metabase/Chatbot PHẢI kết nối:
-- - JDBC URL: jdbc:trino://localhost:8085/delta
-- - Catalog: delta (KHÔNG phải hive)
-- - Database: gold

-- Example 1: Dashboard - Today's overview
-- SELECT * FROM delta.gold.latest_metrics;

-- Example 2: Chatbot - "Which states have highest fraud?"
-- SELECT * FROM delta.gold.state_summary ORDER BY fraud_rate DESC LIMIT 10;

-- Example 3: Chatbot - "Show fraud patterns by amount"
-- SELECT * FROM delta.gold.fraud_patterns;

-- Example 4: Dashboard - Weekly trend
-- SELECT report_date, fraud_rate FROM delta.gold.daily_summary 
-- WHERE report_date >= CURRENT_DATE - INTERVAL '7' DAY
-- ORDER BY report_date;

-- Example 5: Chatbot - "List transactions for customer X"
-- SELECT f.*, c.first_name, c.last_name, m.merchant
-- FROM delta.gold.fact_transactions f
-- JOIN delta.gold.dim_customer c ON f.customer_key = c.customer_key
-- JOIN delta.gold.dim_merchant m ON f.merchant_key = m.merchant_key
-- WHERE c.customer_key = '12345'
-- ORDER BY f.transaction_timestamp DESC
-- LIMIT 20;

-- Example 6: Metabase Dashboard - Fraud rate by hour
-- SELECT hour, fraud_rate 
-- FROM delta.gold.hourly_summary
-- WHERE year = YEAR(CURRENT_DATE) 
--   AND month = MONTH(CURRENT_DATE)
--   AND day = DAY(CURRENT_DATE)
-- ORDER BY hour;

-- Example 7: Chatbot - "Top 5 risky categories today"
-- SELECT category, fraud_rate, fraud_transactions
-- FROM delta.gold.category_summary
-- ORDER BY fraud_rate DESC
-- LIMIT 5;
