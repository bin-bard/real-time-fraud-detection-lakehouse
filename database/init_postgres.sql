-- Khởi tạo database cho hệ thống Fraud Detection với Sparkov dataset
-- Sử dụng IF NOT EXISTS để tránh lỗi khi database đã tồn tại
SELECT 'CREATE DATABASE frauddb'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'frauddb')\gexec

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
-- FIX: Thêm UNIQUE constraint trên trans_num để tránh duplicate
CREATE TABLE IF NOT EXISTS fraud_predictions (
    id SERIAL PRIMARY KEY,
    trans_num VARCHAR(100) UNIQUE NOT NULL,  -- FIX: UNIQUE để tránh duplicate
    prediction_score NUMERIC(5, 4),
    is_fraud_predicted SMALLINT,
    model_version VARCHAR(50),
    prediction_time TIMESTAMP DEFAULT NOW()
);

-- Index để query nhanh
CREATE INDEX IF NOT EXISTS idx_fraud_predictions_time ON fraud_predictions(prediction_time DESC);

-- Bảng chat_history cho chatbot (v2.0)
CREATE TABLE IF NOT EXISTS chat_history (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(100) NOT NULL,
    role VARCHAR(20) NOT NULL,  -- 'user' or 'assistant'
    message TEXT NOT NULL,
    sql_query TEXT,  -- SQL query được sinh ra (nếu có)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_chat_history_session ON chat_history(session_id, created_at);
CREATE INDEX IF NOT EXISTS idx_chat_history_created ON chat_history(created_at);

-- Bảng checkpoint cho data producer (tracking CSV processing progress)
CREATE TABLE IF NOT EXISTS producer_checkpoint (
    id INTEGER PRIMARY KEY DEFAULT 1,
    last_line_processed INTEGER NOT NULL DEFAULT 0,
    last_trans_num VARCHAR(100),
    updated_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT single_row_check CHECK (id = 1)
);

-- Insert initial checkpoint record
INSERT INTO producer_checkpoint (id, last_line_processed) 
VALUES (1, 0)
ON CONFLICT (id) DO NOTHING;

-- Grant permissions
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO postgres;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO postgres;
