-- ============================================================
-- DASHBOARD SQL QUERIES FOR FRAUD DETECTION
-- Real-Time Fraud Detection Lakehouse Project
-- Dataset: Sparkov Credit Card Transactions (2019-2020)
-- ============================================================

-- 1. OVERVIEW METRICS
-- ============================================================

-- 1.1. Total Transactions Overview
SELECT COUNT(*) as total_transactions, SUM(transaction_amount) as total_amount, 
       AVG(transaction_amount) as avg_amount FROM delta.gold.fact_transactions;

-- 1.2. Overall Fraud Rate
SELECT COUNT(*) as total, SUM(CASE WHEN is_fraud=1 THEN 1 ELSE 0 END) as frauds,
       CAST(SUM(CASE WHEN is_fraud=1 THEN 1 ELSE 0 END) AS DOUBLE)/COUNT(*)*100 as fraud_rate_percent
FROM delta.gold.fact_transactions;

-- 1.3. High Risk Transactions
SELECT COUNT(*) as high_risk_count, SUM(transaction_amount) as high_risk_amount
FROM delta.gold.fact_transactions
WHERE is_fraud=1 AND (transaction_amount>1000 OR distance_km>200 OR is_late_night=1);


-- 2. FRAUD TRENDS
-- ============================================================

-- 2.1. Fraud Rate by Hour
SELECT transaction_hour as hour, COUNT(*) as total,
       SUM(CASE WHEN is_fraud=1 THEN 1 ELSE 0 END) as frauds,
       CAST(SUM(CASE WHEN is_fraud=1 THEN 1 ELSE 0 END) AS DOUBLE)/COUNT(*)*100 as fraud_rate
FROM delta.gold.fact_transactions GROUP BY transaction_hour ORDER BY hour;

-- 2.2. Monthly Fraud Trend
SELECT YEAR(transaction_timestamp) as year, MONTH(transaction_timestamp) as month,
       COUNT(*) as total, SUM(CASE WHEN is_fraud=1 THEN 1 ELSE 0 END) as frauds,
       CAST(SUM(CASE WHEN is_fraud=1 THEN 1 ELSE 0 END) AS DOUBLE)/COUNT(*)*100 as fraud_rate
FROM delta.gold.fact_transactions 
GROUP BY YEAR(transaction_timestamp), MONTH(transaction_timestamp) ORDER BY year, month;


-- 3. GEOGRAPHIC ANALYSIS
-- ============================================================

-- 3.1. Fraud by State (Top 20)
SELECT c.customer_state as state, COUNT(*) as total,
       SUM(CASE WHEN f.is_fraud=1 THEN 1 ELSE 0 END) as frauds,
       CAST(SUM(CASE WHEN f.is_fraud=1 THEN 1 ELSE 0 END) AS DOUBLE)/COUNT(*)*100 as fraud_rate
FROM delta.gold.fact_transactions f
JOIN delta.gold.dim_customer c ON f.customer_key=c.customer_key
GROUP BY c.customer_state ORDER BY fraud_rate DESC LIMIT 20;

-- 3.2. Fraud by Distance Range
SELECT CASE WHEN distance_km<10 THEN '0-10km' WHEN distance_km<50 THEN '10-50km'
            WHEN distance_km<100 THEN '50-100km' WHEN distance_km<200 THEN '100-200km'
            ELSE '200+km' END as distance_range,
       COUNT(*) as total, SUM(CASE WHEN is_fraud=1 THEN 1 ELSE 0 END) as frauds,
       CAST(SUM(CASE WHEN is_fraud=1 THEN 1 ELSE 0 END) AS DOUBLE)/COUNT(*)*100 as fraud_rate
FROM delta.gold.fact_transactions WHERE distance_km>=0
GROUP BY CASE WHEN distance_km<10 THEN '0-10km' WHEN distance_km<50 THEN '10-50km'
              WHEN distance_km<100 THEN '50-100km' WHEN distance_km<200 THEN '100-200km'
              ELSE '200+km' END;


-- 4. MERCHANT & CATEGORY
-- ============================================================

-- 4.1. Top Risky Merchants
SELECT merchant, transaction_category, COUNT(*) as total,
       SUM(CASE WHEN is_fraud=1 THEN 1 ELSE 0 END) as frauds,
       CAST(SUM(CASE WHEN is_fraud=1 THEN 1 ELSE 0 END) AS DOUBLE)/COUNT(*)*100 as fraud_rate
FROM delta.gold.fact_transactions
GROUP BY merchant, transaction_category HAVING COUNT(*)>50
ORDER BY fraud_rate DESC LIMIT 20;

-- 4.2. Fraud by Category
SELECT transaction_category, COUNT(*) as total,
       SUM(CASE WHEN is_fraud=1 THEN 1 ELSE 0 END) as frauds,
       CAST(SUM(CASE WHEN is_fraud=1 THEN 1 ELSE 0 END) AS DOUBLE)/COUNT(*)*100 as fraud_rate
FROM delta.gold.fact_transactions
GROUP BY transaction_category ORDER BY fraud_rate DESC;


-- 5. AMOUNT ANALYSIS
-- ============================================================

-- 5.1. Fraud by Amount Range
SELECT CASE amount_bin WHEN 1 THEN '$0-$100' WHEN 2 THEN '$100-$300'
            WHEN 3 THEN '$300-$500' WHEN 4 THEN '$500-$1000' WHEN 5 THEN '$1000+' END as range,
       COUNT(*) as total, SUM(CASE WHEN is_fraud=1 THEN 1 ELSE 0 END) as frauds,
       CAST(SUM(CASE WHEN is_fraud=1 THEN 1 ELSE 0 END) AS DOUBLE)/COUNT(*)*100 as fraud_rate
FROM delta.gold.fact_transactions GROUP BY amount_bin ORDER BY amount_bin;

-- 5.2. High Value Transactions (>$1000)
SELECT transaction_key, transaction_timestamp, transaction_amount, merchant, is_fraud
FROM delta.gold.fact_transactions WHERE transaction_amount>1000
ORDER BY transaction_amount DESC LIMIT 100;


-- 6. TIME PATTERNS
-- ============================================================

-- 6.1. Weekend vs Weekday
SELECT CASE WHEN is_weekend_transaction=1 THEN 'Weekend' ELSE 'Weekday' END as day_type,
       COUNT(*) as total, SUM(CASE WHEN is_fraud=1 THEN 1 ELSE 0 END) as frauds,
       CAST(SUM(CASE WHEN is_fraud=1 THEN 1 ELSE 0 END) AS DOUBLE)/COUNT(*)*100 as fraud_rate
FROM delta.gold.fact_transactions GROUP BY is_weekend_transaction;

-- 6.2. Late Night Analysis
SELECT transaction_hour, COUNT(*) as total,
       SUM(CASE WHEN is_fraud=1 THEN 1 ELSE 0 END) as frauds,
       CAST(SUM(CASE WHEN is_fraud=1 THEN 1 ELSE 0 END) AS DOUBLE)/COUNT(*)*100 as fraud_rate
FROM delta.gold.fact_transactions WHERE is_late_night=1
GROUP BY transaction_hour ORDER BY transaction_hour;


-- 7. CUSTOMER DEMOGRAPHICS
-- ============================================================

-- 7.1. Fraud by Age Group
SELECT CASE WHEN customer_age_at_transaction<25 THEN '18-24'
            WHEN customer_age_at_transaction<35 THEN '25-34'
            WHEN customer_age_at_transaction<45 THEN '35-44'
            WHEN customer_age_at_transaction<55 THEN '45-54'
            WHEN customer_age_at_transaction<65 THEN '55-64' ELSE '65+' END as age_group,
       COUNT(*) as total, SUM(CASE WHEN is_fraud=1 THEN 1 ELSE 0 END) as frauds,
       CAST(SUM(CASE WHEN is_fraud=1 THEN 1 ELSE 0 END) AS DOUBLE)/COUNT(*)*100 as fraud_rate
FROM delta.gold.fact_transactions WHERE customer_age_at_transaction>0
GROUP BY CASE WHEN customer_age_at_transaction<25 THEN '18-24'
              WHEN customer_age_at_transaction<35 THEN '25-34'
              WHEN customer_age_at_transaction<45 THEN '35-44'
              WHEN customer_age_at_transaction<55 THEN '45-54'
              WHEN customer_age_at_transaction<65 THEN '55-64' ELSE '65+' END;


-- 8. MODEL PERFORMANCE
-- ============================================================

-- 8.1. Model Accuracy
SELECT COUNT(*) as total, 
       SUM(CASE WHEN t.is_fraud=p.is_fraud_predicted THEN 1 ELSE 0 END) as correct,
       CAST(SUM(CASE WHEN t.is_fraud=p.is_fraud_predicted THEN 1 ELSE 0 END) AS DOUBLE)/COUNT(*)*100 as accuracy
FROM postgres.public.fraud_predictions p
JOIN postgres.public.transactions t ON p.trans_num=t.trans_num;

-- 8.2. Prediction Score Distribution
SELECT CASE WHEN prediction_score<0.2 THEN '0-20%' WHEN prediction_score<0.4 THEN '20-40%'
            WHEN prediction_score<0.6 THEN '40-60%' WHEN prediction_score<0.8 THEN '60-80%'
            ELSE '80-100%' END as score_range, COUNT(*) as count
FROM postgres.public.fraud_predictions
GROUP BY CASE WHEN prediction_score<0.2 THEN '0-20%' WHEN prediction_score<0.4 THEN '20-40%'
              WHEN prediction_score<0.6 THEN '40-60%' WHEN prediction_score<0.8 THEN '60-80%'
              ELSE '80-100%' END;


-- 9. FRAUD ALERTS
-- ============================================================

-- 9.1. Top High-Risk Frauds
SELECT transaction_key, transaction_timestamp, transaction_amount, merchant, distance_km,
       CASE WHEN transaction_amount>1000 AND distance_km>200 THEN 'CRITICAL'
            WHEN transaction_amount>500 AND is_late_night=1 THEN 'HIGH' ELSE 'MEDIUM' END as severity
FROM delta.gold.fact_transactions WHERE is_fraud=1
ORDER BY transaction_amount DESC LIMIT 100;


-- 10. ADVANCED ANALYTICS
-- ============================================================

-- 10.1. Multi-Factor Risk
SELECT CASE WHEN is_high_amount=1 THEN 'High$' ELSE 'Normal$' END as amt,
       CASE WHEN is_distant_transaction=1 THEN 'Distant' ELSE 'Local' END as dist,
       CASE WHEN is_late_night=1 THEN 'Night' ELSE 'Day' END as time,
       COUNT(*) as total, SUM(CASE WHEN is_fraud=1 THEN 1 ELSE 0 END) as frauds,
       CAST(SUM(CASE WHEN is_fraud=1 THEN 1 ELSE 0 END) AS DOUBLE)/COUNT(*)*100 as fraud_rate
FROM delta.gold.fact_transactions
GROUP BY is_high_amount, is_distant_transaction, is_late_night
ORDER BY fraud_rate DESC;
