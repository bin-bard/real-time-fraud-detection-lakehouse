-- Migration script: Ensure sql_query column exists in chat_history
-- Date: 2025-12-10
-- Purpose: Fix SQL query tracking in chat history

-- Step 1: Add sql_query column if not exists
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'chat_history' AND column_name = 'sql_query'
    ) THEN
        ALTER TABLE chat_history ADD COLUMN sql_query TEXT;
    END IF;
END $$;

-- Step 2: Create index for better query performance
CREATE INDEX IF NOT EXISTS idx_chat_history_session ON chat_history(session_id, created_at);

-- Step 3: Verify
SELECT 
    column_name, 
    data_type, 
    is_nullable 
FROM information_schema.columns 
WHERE table_name = 'chat_history'
ORDER BY ordinal_position;
