-- Test Real-Time Fraud Detection Flow
-- Insert test transactions to trigger Debezium CDC → Kafka → Spark Structured Streaming → API → Slack

-- Transaction 1: HIGH RISK (Large amount + distant + late night)
INSERT INTO transactions (
    trans_date_trans_time, cc_num, merchant, category, amt,
    first, last, gender, street, city, state, zip,
    lat, long, city_pop, job, dob, trans_num, unix_time,
    merch_lat, merch_long, is_fraud
) VALUES (
    NOW(), 
    1234567890123456, 
    'Suspicious Electronics Store', 
    'shopping_net', 
    1850.00,  -- High amount
    'John', 
    'Doe', 
    'M', 
    '123 Main St', 
    'New York', 
    'NY', 
    10001,
    40.7128, 
    -74.0060, 
    8000000, 
    'Engineer', 
    '1990-01-01', 
    CONCAT('RT_HIGH_', EXTRACT(EPOCH FROM NOW())::TEXT), 
    EXTRACT(EPOCH FROM NOW()),
    35.0, 
    -120.0,  -- 4000km away (California)
    1  -- Actual fraud
);

-- Transaction 2: MEDIUM RISK (Medium amount + normal distance)
INSERT INTO transactions (
    trans_date_trans_time, cc_num, merchant, category, amt,
    first, last, gender, street, city, state, zip,
    lat, long, city_pop, job, dob, trans_num, unix_time,
    merch_lat, merch_long, is_fraud
) VALUES (
    NOW(), 
    2345678901234567, 
    'Regular Grocery Store', 
    'grocery_pos', 
    350.00,  -- Medium amount
    'Jane', 
    'Smith', 
    'F', 
    '456 Oak Ave', 
    'Los Angeles', 
    'CA', 
    90001,
    34.0522, 
    -118.2437, 
    4000000, 
    'Teacher', 
    '1985-05-15', 
    CONCAT('RT_MEDIUM_', EXTRACT(EPOCH FROM NOW())::TEXT), 
    EXTRACT(EPOCH FROM NOW()),
    34.0700, 
    -118.2600,  -- 3km away (same city)
    1  -- Actual fraud
);

-- Transaction 3: LOW RISK (Small amount + close distance)
INSERT INTO transactions (
    trans_date_trans_time, cc_num, merchant, category, amt,
    first, last, gender, street, city, state, zip,
    lat, long, city_pop, job, dob, trans_num, unix_time,
    merch_lat, merch_long, is_fraud
) VALUES (
    NOW(), 
    3456789012345678, 
    'Local Coffee Shop', 
    'food_dining', 
    85.00,  -- Low amount
    'Bob', 
    'Johnson', 
    'M', 
    '789 Pine St', 
    'Seattle', 
    'WA', 
    98101,
    47.6062, 
    -122.3321, 
    750000, 
    'Developer', 
    '1992-08-20', 
    CONCAT('RT_LOW_', EXTRACT(EPOCH FROM NOW())::TEXT), 
    EXTRACT(EPOCH FROM NOW()),
    47.6070, 
    -122.3340,  -- 1km away
    1  -- Actual fraud
);

-- Transaction 4: NORMAL (Not fraud)
INSERT INTO transactions (
    trans_date_trans_time, cc_num, merchant, category, amt,
    first, last, gender, street, city, state, zip,
    lat, long, city_pop, job, dob, trans_num, unix_time,
    merch_lat, merch_long, is_fraud
) VALUES (
    NOW(), 
    4567890123456789, 
    'Gas Station', 
    'gas_transport', 
    45.00,  -- Low amount
    'Alice', 
    'Williams', 
    'F', 
    '321 Maple Dr', 
    'Chicago', 
    'IL', 
    60601,
    41.8781, 
    -87.6298, 
    2700000, 
    'Designer', 
    '1988-03-10', 
    CONCAT('RT_NORMAL_', EXTRACT(EPOCH FROM NOW())::TEXT), 
    EXTRACT(EPOCH FROM NOW()),
    41.8800, 
    -87.6350,  -- 1km away
    0  -- Not fraud
);

-- Verify insertions
SELECT 
    trans_num,
    amt,
    merchant,
    city,
    is_fraud,
    trans_date_trans_time
FROM transactions
WHERE trans_num LIKE 'RT_%'
ORDER BY trans_date_trans_time DESC
LIMIT 10;
