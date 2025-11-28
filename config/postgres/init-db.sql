-- Create schema for credit card transactions
CREATE SCHEMA IF NOT EXISTS public;

-- Create table for credit card transactions
CREATE TABLE IF NOT EXISTS public.transactions (
    id SERIAL PRIMARY KEY,
    time_seconds DOUBLE PRECISION NOT NULL,
    v1 DOUBLE PRECISION,
    v2 DOUBLE PRECISION,
    v3 DOUBLE PRECISION,
    v4 DOUBLE PRECISION,
    v5 DOUBLE PRECISION,
    v6 DOUBLE PRECISION,
    v7 DOUBLE PRECISION,
    v8 DOUBLE PRECISION,
    v9 DOUBLE PRECISION,
    v10 DOUBLE PRECISION,
    v11 DOUBLE PRECISION,
    v12 DOUBLE PRECISION,
    v13 DOUBLE PRECISION,
    v14 DOUBLE PRECISION,
    v15 DOUBLE PRECISION,
    v16 DOUBLE PRECISION,
    v17 DOUBLE PRECISION,
    v18 DOUBLE PRECISION,
    v19 DOUBLE PRECISION,
    v20 DOUBLE PRECISION,
    v21 DOUBLE PRECISION,
    v22 DOUBLE PRECISION,
    v23 DOUBLE PRECISION,
    v24 DOUBLE PRECISION,
    v25 DOUBLE PRECISION,
    v26 DOUBLE PRECISION,
    v27 DOUBLE PRECISION,
    v28 DOUBLE PRECISION,
    amount DOUBLE PRECISION NOT NULL,
    class INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create index on time_seconds for faster queries
CREATE INDEX IF NOT EXISTS idx_transactions_time ON public.transactions(time_seconds);

-- Create index on class for fraud analysis
CREATE INDEX IF NOT EXISTS idx_transactions_class ON public.transactions(class);

-- Create index on created_at for time-based queries
CREATE INDEX IF NOT EXISTS idx_transactions_created_at ON public.transactions(created_at);

-- Grant permissions
GRANT ALL PRIVILEGES ON DATABASE transactions TO postgres;
GRANT ALL PRIVILEGES ON SCHEMA public TO postgres;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO postgres;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO postgres;
