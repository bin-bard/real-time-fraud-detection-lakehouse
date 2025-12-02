# Metabase Configuration for Fraud Detection Lakehouse

## ✅ Status: Ready for Metabase Connection

All Delta Lake tables have been successfully registered to Hive Metastore and are queryable via Trino.

## 📊 Available Tables

### Bronze Layer (Raw CDC Data)
- `delta.bronze.transactions` - 25,000+ records

### Silver Layer (Feature Engineered)
- `delta.silver.transactions` - 25,000+ records

### Gold Layer (Star Schema for Analytics)
**Dimension Tables:**
- `delta.gold.dim_customer` - Customer dimension
- `delta.gold.dim_merchant` - Merchant dimension  
- `delta.gold.dim_time` - Time dimension
- `delta.gold.dim_location` - Location dimension

**Fact Table:**
- `delta.gold.fact_transactions` - 25,000+ transaction facts

---

## 🔧 Metabase Connection Settings

### Database Configuration

```yaml
Database Type: Trino
Display Name: Fraud Detection Lakehouse

Connection Settings:
  Host: trino
  Port: 8081
  Catalog: delta
  Database: gold        # or 'bronze'/'silver' for raw data
  
Authentication:
  Username: (leave empty)
  Password: (leave empty)
  
Advanced Options:
  SSL: No
```

### Important Notes:
- **Host**: Use `trino` (Docker service name) if Metabase runs in same Docker network
- **Host**: Use `localhost` if Metabase runs outside Docker
- **Port**: Internal port is `8081`, external is `8085`
- **Default Database**: Start with `gold` for star schema analytics

---

## 📈 Sample Queries for Fraud Detection Dashboards

> **⚠️ Important Notes:**
> - **Trino Syntax**: DO NOT use semicolons (`;`) at the end of queries - Trino will throw error
> - **Boolean Values**: Use `is_fraud = 1` (not `is_fraud = true`) - stored as INTEGER
> - **Column Names**: 
>   - Use `transaction_amount` (not `amt`)
>   - Use `transaction_category` (not `category`)
>   - Fact table stores attributes directly (denormalized) - some dimensions only used for enrichment
> - All queries below are tested and ready to use in Metabase

### 1. Fraud Transactions by Category
```sql
SELECT 
    transaction_category,
    COUNT(*) as total_transactions,
    SUM(CASE WHEN is_fraud = 1 THEN 1 ELSE 0 END) as fraud_count,
    ROUND(100.0 * SUM(CASE WHEN is_fraud = 1 THEN 1 ELSE 0 END) / COUNT(*), 2) as fraud_rate
FROM delta.gold.fact_transactions
GROUP BY transaction_category
ORDER BY fraud_rate DESC
```

### 2. Top 10 High-Risk Merchants
```sql
SELECT 
    merchant,
    transaction_category,
    COUNT(*) as total_txn,
    SUM(CASE WHEN is_fraud = 1 THEN 1 ELSE 0 END) as fraud_txn,
    ROUND(AVG(transaction_amount), 2) as avg_amount,
    ROUND(100.0 * SUM(CASE WHEN is_fraud = 1 THEN 1 ELSE 0 END) / COUNT(*), 2) as fraud_rate
FROM delta.gold.fact_transactions
GROUP BY merchant, transaction_category
HAVING COUNT(*) >= 10
ORDER BY fraud_rate DESC
LIMIT 10
```

### 3. Fraud Trends Over Time
```sql
SELECT 
    YEAR(transaction_timestamp) as year,
    MONTH(transaction_timestamp) as month,
    DATE_FORMAT(transaction_timestamp, '%M') as month_name,
    COUNT(*) as total_transactions,
    SUM(CASE WHEN is_fraud = 1 THEN 1 ELSE 0 END) as fraud_count,
    ROUND(100.0 * SUM(CASE WHEN is_fraud = 1 THEN 1 ELSE 0 END) / COUNT(*), 2) as fraud_rate,
    ROUND(AVG(transaction_amount), 2) as avg_transaction_amount
FROM delta.gold.fact_transactions
GROUP BY YEAR(transaction_timestamp), MONTH(transaction_timestamp), DATE_FORMAT(transaction_timestamp, '%M')
ORDER BY year, month
```

### 4. Geographic Fraud Distribution
```sql
SELECT 
    dc.customer_state as state,
    dc.customer_city as city,
    COUNT(*) as total_transactions,
    SUM(CASE WHEN ft.is_fraud = 1 THEN 1 ELSE 0 END) as fraud_count,
    ROUND(100.0 * SUM(CASE WHEN ft.is_fraud = 1 THEN 1 ELSE 0 END) / COUNT(*), 2) as fraud_rate,
    ROUND(AVG(ft.transaction_amount), 2) as avg_amount
FROM delta.gold.fact_transactions ft
JOIN delta.gold.dim_customer dc ON ft.customer_key = dc.customer_key
GROUP BY dc.customer_state, dc.customer_city
HAVING COUNT(*) >= 10
ORDER BY fraud_rate DESC
LIMIT 20
```

### 5. Customer Risk Profile
```sql
SELECT 
    dc.gender,
    COUNT(DISTINCT dc.customer_key) as total_customers,
    COUNT(*) as total_transactions,
    SUM(CASE WHEN ft.is_fraud = 1 THEN 1 ELSE 0 END) as fraud_count,
    ROUND(100.0 * SUM(CASE WHEN ft.is_fraud = 1 THEN 1 ELSE 0 END) / COUNT(*), 2) as fraud_rate,
    ROUND(AVG(ft.transaction_amount), 2) as avg_transaction_amount
FROM delta.gold.fact_transactions ft
JOIN delta.gold.dim_customer dc ON ft.customer_key = dc.customer_key
GROUP BY dc.gender
ORDER BY fraud_rate DESC
```

### 6. Transaction Amount Distribution by Fraud Status
```sql
SELECT 
    CASE 
        WHEN transaction_amount < 50 THEN '0-50'
        WHEN transaction_amount < 100 THEN '50-100'
        WHEN transaction_amount < 200 THEN '100-200'
        WHEN transaction_amount < 500 THEN '200-500'
        ELSE '500+'
    END as amount_range,
    COUNT(*) as total_transactions,
    SUM(CASE WHEN is_fraud = 1 THEN 1 ELSE 0 END) as fraud_count,
    ROUND(100.0 * SUM(CASE WHEN is_fraud = 1 THEN 1 ELSE 0 END) / COUNT(*), 2) as fraud_rate
FROM delta.gold.fact_transactions
GROUP BY 
    CASE 
        WHEN transaction_amount < 50 THEN '0-50'
        WHEN transaction_amount < 100 THEN '50-100'
        WHEN transaction_amount < 200 THEN '100-200'
        WHEN transaction_amount < 500 THEN '200-500'
        ELSE '500+'
    END
ORDER BY fraud_rate DESC
```

### 7. Real-time Fraud Detection Rate (Last 24 Hours)
```sql
SELECT 
    transaction_hour as hour,
    COUNT(*) as transactions,
    SUM(CASE WHEN is_fraud = 1 THEN 1 ELSE 0 END) as frauds,
    ROUND(100.0 * SUM(CASE WHEN is_fraud = 1 THEN 1 ELSE 0 END) / COUNT(*), 2) as fraud_rate
FROM delta.gold.fact_transactions
WHERE transaction_timestamp >= CURRENT_TIMESTAMP - INTERVAL '1' DAY
GROUP BY transaction_hour
ORDER BY transaction_hour
```

---

## 🎨 Dashboard Recommendations

### 1. Executive Summary Dashboard
- **KPIs**: Total transactions, fraud count, fraud rate, total loss amount
- **Charts**: 
  - Fraud trends line chart (monthly)
  - Category fraud rate bar chart
  - Geographic heatmap

### 2. Merchant Analysis Dashboard
- **Top merchants by fraud rate** (table)
- **Category breakdown** (pie chart)
- **Merchant risk matrix** (scatter plot: volume vs fraud rate)

### 3. Customer Behavior Dashboard
- **Customer demographics** (bar charts)
- **Transaction patterns** (time series)
- **Risk segmentation** (funnel chart)

### 4. Geographic Risk Dashboard
- **State-level fraud map** (choropleth)
- **Top risky cities** (table)
- **Regional trends** (line charts)

### 5. Real-time Monitoring Dashboard
- **Live transaction feed** (last 100 transactions)
- **Hourly fraud rate** (gauge)
- **Alert threshold indicators**

---

## 🔄 Data Refresh

Tables are automatically refreshed:
- **Bronze**: Real-time CDC from Kafka
- **Silver**: Processed every 30 seconds
- **Gold**: Updated every 60 seconds

Metabase queries will always show latest data (no caching needed for star schema).

---

## ✅ Verification Commands

```bash
# Check all available catalogs
docker exec trino trino --server localhost:8081 --execute "SHOW CATALOGS"

# Check all schemas in delta catalog
docker exec trino trino --server localhost:8081 --execute "SHOW SCHEMAS FROM delta"

# Check Gold layer tables
docker exec trino trino --server localhost:8081 --execute "SHOW TABLES FROM delta.gold"

# Sample data from fact table
docker exec trino trino --server localhost:8081 --execute "SELECT * FROM delta.gold.fact_transactions LIMIT 5"

# Check record counts
docker exec trino trino --server localhost:8081 --execute "
SELECT 
    'bronze.transactions' as table_name, COUNT(*) as records FROM delta.bronze.transactions
UNION ALL
SELECT 
    'silver.transactions', COUNT(*) FROM delta.silver.transactions
UNION ALL
SELECT 
    'gold.fact_transactions', COUNT(*) FROM delta.gold.fact_transactions
"
```

---

## 🚀 Quick Start Guide

1. **Start Metabase** (if not running):
   ```bash
   docker-compose up -d metabase
   ```

2. **Access Metabase UI**:
   ```
   http://localhost:3000
   ```

3. **Add Database**:
   - Settings → Admin → Databases → Add Database
   - Select "Trino"
   - Fill in connection settings (see above)
   - Test connection
   - Save

4. **Browse Data**:
   - Click "Browse Data"
   - Select "Fraud Detection Lakehouse"
   - Explore `gold` schema tables

5. **Create Your First Question**:
   - New → Question
   - Select fact_transactions table
   - Add filters, aggregations, joins
   - Visualize

---

## 🐛 Troubleshooting

### Connection Failed
- **Check Trino status**: `docker ps | grep trino`
- **Check Trino logs**: `docker logs trino --tail 50`
- **Verify port**: Ensure port 8085 is exposed if accessing externally

### Tables Not Visible
- **Verify registration**: `docker logs hive-registration --tail 30`
- **Check Hive Metastore**: `docker logs hive-metastore --tail 30`
- **Re-register**: `docker-compose restart hive-registration`

### Query Errors
- **Check Trino query logs**: Look in Trino logs for SQL errors
- **Verify table schema**: `DESCRIBE delta.gold.fact_transactions`
- **Test simple query first**: `SELECT COUNT(*) FROM delta.gold.fact_transactions`

---

## 📝 Notes

- All tables use **Delta Lake** format with ACID guarantees
- Tables are **externally managed** - data lives in MinIO S3
- Hive Metastore provides **metadata layer** for Trino
- **No SerDe warnings** in logs are normal for Delta tables
- Automatic **hourly re-registration** keeps metadata fresh

---

## 🎯 Ready to Visualize!

Your Fraud Detection Lakehouse is now **fully operational** and ready for Metabase dashboards. Start building visualizations using the sample queries above or create your own custom analyses.

**Happy Analyzing! 📊✨**
