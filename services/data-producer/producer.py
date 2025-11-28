import csv
import time
import psycopg2
import os

# --- Cấu hình ---
DB_HOST = os.environ.get("DB_HOST", "postgres-db")
DB_PORT = os.environ.get("DB_PORT", "5432")
DB_NAME = os.environ.get("DB_NAME", "transactions")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "postgres")
DATA_FILE = "/data/creditcard.csv"
# Hệ số co giãn thời gian. Ví dụ: 0.01 nghĩa là 1 giây trong dữ liệu gốc = 0.01 giây trong mô phỏng.
# Điều này giúp chạy hết bộ dữ liệu 2 ngày trong vài giờ thay vì 2 ngày thật.
TIME_SCALING_FACTOR = 0.01 

# --- Khởi tạo PostgreSQL Connection ---
conn = None
while conn is None:
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        print("PostgreSQL connection established successfully!")
    except Exception as e:
        print(f"Could not connect to PostgreSQL, retrying in 5 seconds... Error: {e}")
        time.sleep(5)

# --- Đọc và insert dữ liệu theo thời gian ---
def simulate_real_time_stream():
    print(f"Simulating real-time stream from {DATA_FILE}...")
    cursor = conn.cursor()
    
    try:
        with open(DATA_FILE, 'r') as file:
            reader = csv.DictReader(file)
            last_transaction_time = 0
            
            # Đọc dòng đầu tiên để khởi tạo thời gian
            first_row = next(reader)
            last_transaction_time = float(first_row['Time'])
            
            # Xử lý và insert dòng đầu tiên
            insert_transaction(cursor, 1, first_row)

            # Xử lý các dòng còn lại
            for i, row in enumerate(reader, start=2):
                current_transaction_time = float(row['Time'])
                
                # Tính toán thời gian chờ
                time_diff = current_transaction_time - last_transaction_time
                wait_time = time_diff * TIME_SCALING_FACTOR
                
                if wait_time > 0:
                    time.sleep(wait_time)
                
                # Insert giao dịch
                insert_transaction(cursor, i, row)
                
                last_transaction_time = current_transaction_time

    except FileNotFoundError:
        print(f"Error: Data file not found at {DATA_FILE}.")
    except Exception as e:
        print(f"An error occurred during simulation: {e}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
            print("PostgreSQL connection closed.")

def insert_transaction(cursor, index, row_data):
    """Helper function to process and insert a single transaction."""
    try:
        # Prepare insert query
        insert_query = """
            INSERT INTO public.transactions (
                time_seconds, v1, v2, v3, v4, v5, v6, v7, v8, v9, v10,
                v11, v12, v13, v14, v15, v16, v17, v18, v19, v20,
                v21, v22, v23, v24, v25, v26, v27, v28, amount, class
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
        """
        
        # Convert data
        values = (
            float(row_data['Time']),
            float(row_data['V1']), float(row_data['V2']), float(row_data['V3']), 
            float(row_data['V4']), float(row_data['V5']), float(row_data['V6']), 
            float(row_data['V7']), float(row_data['V8']), float(row_data['V9']), 
            float(row_data['V10']), float(row_data['V11']), float(row_data['V12']), 
            float(row_data['V13']), float(row_data['V14']), float(row_data['V15']), 
            float(row_data['V16']), float(row_data['V17']), float(row_data['V18']), 
            float(row_data['V19']), float(row_data['V20']), float(row_data['V21']), 
            float(row_data['V22']), float(row_data['V23']), float(row_data['V24']), 
            float(row_data['V25']), float(row_data['V26']), float(row_data['V27']), 
            float(row_data['V28']), float(row_data['Amount']), int(float(row_data['Class']))
        )
        
        # Execute insert
        cursor.execute(insert_query, values)
        conn.commit()
        
        print(f"Inserted transaction #{index} | Time: {row_data['Time']}")
    except (ValueError, TypeError) as e:
        print(f"Skipping row #{index} due to data conversion error: {e}")
    except Exception as e:
        print(f"Error inserting transaction #{index}: {e}")
        conn.rollback()

if __name__ == "__main__":
    simulate_real_time_stream()