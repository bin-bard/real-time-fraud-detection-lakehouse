-- Khởi tạo database cho hệ thống Fraud Detection với Sparkov dataset
CREATE DATABASE frauddb;
\connect frauddb;

-- Tạo schemas
CREATE SCHEMA IF NOT EXISTS public;

-- Bảng transactions với schema Sparkov
CREATE TABLE IF NOT EXISTS transactions (
    -- Transaction information
    trans_date_trans_time TIMESTAMP NOT NULL,
    cc_num BIGINT NOT NULL,
    merchant VARCHAR(255) NOT NULL,
    category VARCHAR(100) NOT NULL,
    amt NUMERIC(10, 2) NOT NULL,
    
    -- Customer information
    first VARCHAR(100),
    last VARCHAR(100),
    gender CHAR(1),
    street VARCHAR(255),
    city VARCHAR(100),
    state VARCHAR(50),
    zip INTEGER,
    
    -- Customer location
    lat DOUBLE PRECISION NOT NULL,
    long DOUBLE PRECISION NOT NULL,
    
    -- Additional customer info
    city_pop INTEGER,
    job VARCHAR(200),
    dob DATE,
    
    -- Transaction metadata
    trans_num VARCHAR(100) PRIMARY KEY,
    unix_time BIGINT,
    
    -- Merchant location
    merch_lat DOUBLE PRECISION NOT NULL,
    merch_long DOUBLE PRECISION NOT NULL,
    
    -- Fraud label
    is_fraud SMALLINT NOT NULL DEFAULT 0,
    
    -- Audit columns
    created_at TIMESTAMP DEFAULT NOW()
);

-- Tạo indexes để tối ưu query performance
CREATE INDEX idx_transactions_trans_time ON transactions(trans_date_trans_time);
CREATE INDEX idx_transactions_cc_num ON transactions(cc_num);
CREATE INDEX idx_transactions_is_fraud ON transactions(is_fraud);
CREATE INDEX idx_transactions_category ON transactions(category);
CREATE INDEX idx_transactions_state ON transactions(state);
CREATE INDEX idx_transactions_merchant ON transactions(merchant);
CREATE INDEX idx_transactions_amt ON transactions(amt);

-- Composite index cho fraud analysis
CREATE INDEX idx_fraud_analysis ON transactions(is_fraud, trans_date_trans_time, amt);

-- Bảng để lưu fraud predictions từ ML model (optional - cho real-time scoring)
CREATE TABLE IF NOT EXISTS fraud_predictions (
    id SERIAL PRIMARY KEY,
    trans_num VARCHAR(100) REFERENCES transactions(trans_num),
    prediction_score NUMERIC(5, 4),
    is_fraud_predicted SMALLINT,
    model_version VARCHAR(50),
    prediction_time TIMESTAMP DEFAULT NOW()
);

-- Grant permissions
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO postgres;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO postgres;
