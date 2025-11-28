import pandas as pd
import psycopg2
from psycopg2.extras import execute_batch
import os
import time

# --- Configuration ---
DB_HOST = os.environ.get("DB_HOST", "postgres-db")
DB_PORT = os.environ.get("DB_PORT", "5432")
DB_NAME = os.environ.get("DB_NAME", "transactions")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "postgres")
DATA_FILE = "/data/creditcard.csv"

def wait_for_postgres():
    """Wait for PostgreSQL to be ready"""
    max_retries = 30
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            conn = psycopg2.connect(
                host=DB_HOST,
                port=DB_PORT,
                database=DB_NAME,
                user=DB_USER,
                password=DB_PASSWORD
            )
            conn.close()
            print("PostgreSQL is ready!")
            return True
        except psycopg2.OperationalError:
            retry_count += 1
            print(f"Waiting for PostgreSQL... ({retry_count}/{max_retries})")
            time.sleep(2)
    
    raise Exception("Could not connect to PostgreSQL")

def load_csv_to_postgres():
    """Load CSV data into PostgreSQL"""
    print(f"Loading data from {DATA_FILE}...")
    
    # Wait for PostgreSQL
    wait_for_postgres()
    
    # Read CSV file
    try:
        df = pd.read_csv(DATA_FILE)
        print(f"Loaded {len(df)} rows from CSV")
    except FileNotFoundError:
        print(f"Error: Data file not found at {DATA_FILE}")
        return
    
    # Rename columns to match database schema
    column_mapping = {
        'Time': 'time_seconds',
        'V1': 'v1', 'V2': 'v2', 'V3': 'v3', 'V4': 'v4', 'V5': 'v5',
        'V6': 'v6', 'V7': 'v7', 'V8': 'v8', 'V9': 'v9', 'V10': 'v10',
        'V11': 'v11', 'V12': 'v12', 'V13': 'v13', 'V14': 'v14', 'V15': 'v15',
        'V16': 'v16', 'V17': 'v17', 'V18': 'v18', 'V19': 'v19', 'V20': 'v20',
        'V21': 'v21', 'V22': 'v22', 'V23': 'v23', 'V24': 'v24', 'V25': 'v25',
        'V26': 'v26', 'V27': 'v27', 'V28': 'v28',
        'Amount': 'amount',
        'Class': 'class'
    }
    df = df.rename(columns=column_mapping)
    
    # Connect to PostgreSQL
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    # Check if data already exists
    cursor.execute("SELECT COUNT(*) FROM public.transactions")
    count = cursor.fetchone()[0]
    
    if count > 0:
        print(f"Table already contains {count} rows. Skipping initial load.")
        conn.close()
        return
    
    # Prepare insert query
    columns = list(column_mapping.values())
    insert_query = f"""
        INSERT INTO public.transactions ({', '.join(columns)})
        VALUES ({', '.join(['%s'] * len(columns))})
    """
    
    # Batch insert data
    batch_size = 1000
    total_rows = len(df)
    
    print("Inserting data into PostgreSQL...")
    for i in range(0, total_rows, batch_size):
        batch = df.iloc[i:i+batch_size]
        data = [tuple(row) for row in batch[columns].values]
        
        execute_batch(cursor, insert_query, data)
        conn.commit()
        
        print(f"Inserted {min(i+batch_size, total_rows)}/{total_rows} rows")
    
    cursor.close()
    conn.close()
    
    print("Data loading completed successfully!")

if __name__ == "__main__":
    load_csv_to_postgres()
