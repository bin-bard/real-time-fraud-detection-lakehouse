-- Placeholder init script for Postgres
CREATE DATABASE frauddb;
\connect frauddb;

CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS analytics;

-- Example table
CREATE TABLE IF NOT EXISTS staging.transactions (
    transaction_id BIGINT PRIMARY KEY,
    amount NUMERIC(10,2),
    is_fraud SMALLINT,
    created_at TIMESTAMP DEFAULT NOW()
);
