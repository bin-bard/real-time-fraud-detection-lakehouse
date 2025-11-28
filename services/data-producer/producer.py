import csv
import json
import time
import psycopg2
from psycopg2.extras import execute_values
import os
from datetime import datetime

# --- Cấu hình ---
POSTGRES_HOST = os.environ.get("POSTGRES_HOST", "postgres")
POSTGRES_PORT = os.environ.get("POSTGRES_PORT", "5432")
POSTGRES_DB = os.environ.get("POSTGRES_DB", "frauddb")
POSTGRES_USER = os.environ.get("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "postgres")

DATA_FILE = "/data/fraudTrain.csv"
CHECKPOINT_FILE = "/data/producer_checkpoint.txt"
# Hệ số co giãn thời gian để mô phỏng stream nhanh hơn thực tế
# 0.001 = giao dịch 1 ngày chạy trong vài phút
TIME_SCALING_FACTOR = 0.001 

# --- Khởi tạo PostgreSQL Connection ---
conn = None
while conn is None:
    try:
        conn = psycopg2.connect(
            host=POSTGRES_HOST,
            port=POSTGRES_PORT,
            database=POSTGRES_DB,
            user=POSTGRES_USER,
            password=POSTGRES_PASSWORD
        )
        print("✅ PostgreSQL connected successfully!")
    except Exception as e:
        print(f"Could not connect to PostgreSQL, retrying in 5 seconds... Error: {e}")
        time.sleep(5)

# --- Đọc checkpoint (vị trí đã xử lý) ---
def get_last_checkpoint():
    """Đọc vị trí dòng cuối cùng đã xử lý từ checkpoint file"""
    try:
        with open(CHECKPOINT_FILE, 'r') as f:
            return int(f.read().strip())
    except FileNotFoundError:
        return 0  # Bắt đầu từ đầu nếu chưa có checkpoint

def save_checkpoint(line_number):
    """Lưu vị trí đã xử lý vào checkpoint file"""
    with open(CHECKPOINT_FILE, 'w') as f:
        f.write(str(line_number))

# --- Đọc và gửi dữ liệu theo thời gian ---
def simulate_real_time_stream():
    print(f"🚀 Simulating real-time stream from {DATA_FILE}...")
    cursor = conn.cursor()
    
    # Đọc checkpoint
    start_line = get_last_checkpoint()
    print(f"📍 Resuming from line {start_line}...")
    
    try:
        with open(DATA_FILE, 'r') as file:
            reader = csv.DictReader(file)
            last_transaction_time = None
            
            # Skip các dòng đã xử lý
            for _ in range(start_line):
                next(reader, None)
            
            for i, row in enumerate(reader, start=start_line + 1):
                try:
                    # Parse timestamp
                    current_time_str = row['trans_date_trans_time']
                    current_time = datetime.strptime(current_time_str, '%Y-%m-%d %H:%M:%S')
                    
                    # Tính thời gian chờ giữa các giao dịch
                    if last_transaction_time is not None:
                        time_diff = (current_time - last_transaction_time).total_seconds()
                        wait_time = time_diff * TIME_SCALING_FACTOR
                        if wait_time > 0:
                            time.sleep(wait_time)
                    
                    # Gửi giao dịch vào PostgreSQL
                    send_transaction(cursor, i, row)
                    
                    last_transaction_time = current_time
                    
                    # Commit mỗi 100 transactions
                    if i % 100 == 0:
                        conn.commit()
                        save_checkpoint(i)
                        print(f"📊 Processed {i} transactions...")
                        
                except Exception as e:
                    print(f"⚠️ Error processing row {i}: {e}")
                    conn.rollback()  # Rollback để tránh transaction aborted
                    continue

    except FileNotFoundError:
        print(f"❌ Error: Data file not found at {DATA_FILE}.")
    except Exception as e:
        print(f"❌ An error occurred during simulation: {e}")
    finally:
        if cursor:
            conn.commit()
            save_checkpoint(i if 'i' in locals() else start_line)
            cursor.close()
        if conn:
            conn.close()
            print("✅ PostgreSQL connection closed.")
        print(f"📍 Checkpoint saved at line {i if 'i' in locals() else start_line}")

def send_transaction(cursor, index, row_data):
    """Helper function to process and send a single transaction to PostgreSQL."""
    try:
        # INSERT vào bảng transactions với schema Sparkov
        insert_query = """
            INSERT INTO transactions (
                trans_date_trans_time, cc_num, merchant, category, amt,
                first, last, gender, street, city, state, zip,
                lat, long, city_pop, job, dob, trans_num, unix_time,
                merch_lat, merch_long, is_fraud
            ) VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s
            )
        """
        
        values = (
            row_data['trans_date_trans_time'],
            int(row_data['cc_num']),
            row_data['merchant'],
            row_data['category'],
            float(row_data['amt']),
            row_data['first'],
            row_data['last'],
            row_data['gender'],
            row_data['street'],
            row_data['city'],
            row_data['state'],
            int(row_data['zip']),
            float(row_data['lat']),
            float(row_data['long']),
            int(row_data['city_pop']),
            row_data['job'],
            row_data['dob'],
            row_data['trans_num'],
            int(row_data['unix_time']),
            float(row_data['merch_lat']),
            float(row_data['merch_long']),
            int(row_data['is_fraud'])
        )
        
        cursor.execute(insert_query, values)
        
        if index % 50 == 0:
            print(f"✅ Sent transaction #{index} | Time: {row_data['trans_date_trans_time']} | Amount: ${row_data['amt']} | Fraud: {row_data['is_fraud']}")
            
    except Exception as e:
        print(f"❌ Error sending transaction #{index}: {e}")

if __name__ == "__main__":
    simulate_real_time_stream()