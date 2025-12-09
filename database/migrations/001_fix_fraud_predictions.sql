-- Migration script: Add UNIQUE constraint to fraud_predictions.trans_num
-- Date: 2025-12-10
-- Purpose: Fix duplicate predictions issue

-- Step 1: Drop existing table if needed (backup first if has data!)
-- DROP TABLE IF EXISTS fraud_predictions;

-- Step 2: Recreate with UNIQUE constraint
CREATE TABLE IF NOT EXISTS fraud_predictions (
    id SERIAL PRIMARY KEY,
    trans_num VARCHAR(100) UNIQUE NOT NULL,
    prediction_score NUMERIC(5, 4),
    is_fraud_predicted SMALLINT,
    model_version VARCHAR(50),
    prediction_time TIMESTAMP DEFAULT NOW()
);

-- Step 3: Create index for faster queries
CREATE INDEX IF NOT EXISTS idx_fraud_predictions_time ON fraud_predictions(prediction_time DESC);

-- Step 4: Grant permissions
GRANT ALL PRIVILEGES ON fraud_predictions TO postgres;
GRANT ALL PRIVILEGES ON SEQUENCE fraud_predictions_id_seq TO postgres;

-- Verify
SELECT COUNT(*) as total_predictions FROM fraud_predictions;
