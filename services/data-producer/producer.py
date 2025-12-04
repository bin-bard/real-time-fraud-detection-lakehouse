import csv
import json
import time
import psycopg2
from psycopg2.extras import execute_values
import os
import sys
import argparse
from datetime import datetime

# --- Cấu hình ---
POSTGRES_HOST = os.environ.get("POSTGRES_HOST", "postgres")
POSTGRES_PORT = os.environ.get("POSTGRES_PORT", "5432")
POSTGRES_DB = os.environ.get("POSTGRES_DB", "frauddb")
POSTGRES_USER = os.environ.get("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "postgres")

DATA_FILE = "/data/fraudTrain.csv"
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

# --- Đọc checkpoint từ PostgreSQL ---
def get_last_checkpoint():
    """Đọc vị trí dòng cuối cùng đã xử lý từ PostgreSQL"""
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT last_line_processed, last_trans_num FROM producer_checkpoint WHERE id = 1")
        result = cursor.fetchone()
        cursor.close()
        
        if result:
            line_num, trans_num = result
            print(f"📍 Last checkpoint: Line {line_num}, trans_num: {trans_num}")
            return line_num
        return 0
    except Exception as e:
        print(f"⚠️ Error reading checkpoint: {e}")
        return 0

def save_checkpoint(line_number, trans_num=None):
    """Lưu vị trí đã xử lý vào PostgreSQL"""
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE producer_checkpoint 
            SET last_line_processed = %s, 
                last_trans_num = %s,
                updated_at = NOW()
            WHERE id = 1
        """, (line_number, trans_num))
        conn.commit()
        cursor.close()
    except Exception as e:
        print(f"⚠️ Error saving checkpoint: {e}")
        conn.rollback()

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
                        save_checkpoint(i, row.get('trans_num'))
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
            # Save final checkpoint with last trans_num if available
            final_trans_num = row.get('trans_num') if 'row' in locals() else None
            save_checkpoint(i if 'i' in locals() else start_line, final_trans_num)
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

def bulk_load_transactions(num_records=50000):
    """
    Bulk load initial data for ML training
    Loads num_records quickly without time delay between transactions
    """
    print(f"🚀 BULK LOAD MODE: Loading {num_records} records...")
    cursor = conn.cursor()
    
    # Check checkpoint
    start_line = get_last_checkpoint()
    print(f"📍 Starting from line {start_line}...")
    
    batch_size = 1000  # Insert 1000 records at a time for performance
    batch = []
    records_loaded = 0
    
    try:
        with open(DATA_FILE, 'r') as file:
            reader = csv.DictReader(file)
            
            # Skip processed lines
            for _ in range(start_line):
                next(reader, None)
            
            for i, row in enumerate(reader, start=start_line + 1):
                if records_loaded >= num_records:
                    break
                    
                try:
                    # Prepare values tuple
                    values = (
                        row['trans_date_trans_time'],
                        int(row['cc_num']),
                        row['merchant'],
                        row['category'],
                        float(row['amt']),
                        row['first'],
                        row['last'],
                        row['gender'],
                        row['street'],
                        row['city'],
                        row['state'],
                        int(row['zip']),
                        float(row['lat']),
                        float(row['long']),
                        int(row['city_pop']),
                        row['job'],
                        row['dob'],
                        row['trans_num'],
                        int(row['unix_time']),
                        float(row['merch_lat']),
                        float(row['merch_long']),
                        int(row['is_fraud'])
                    )
                    batch.append(values)
                    records_loaded += 1
                    
                    # Batch insert when batch is full
                    if len(batch) >= batch_size:
                        insert_query = """
                            INSERT INTO transactions (
                                trans_date_trans_time, cc_num, merchant, category, amt,
                                first, last, gender, street, city, state, zip,
                                lat, long, city_pop, job, dob, trans_num, unix_time,
                                merch_lat, merch_long, is_fraud
                            ) VALUES %s
                        """
                        execute_values(cursor, insert_query, batch)
                        conn.commit()
                        
                        save_checkpoint(i, row.get('trans_num'))
                        print(f"✅ Bulk loaded {records_loaded}/{num_records} records...")
                        batch = []
                        
                except Exception as e:
                    print(f"⚠️ Error processing row {i}: {e}")
                    conn.rollback()
                    continue
            
            # Insert remaining batch
            if batch:
                insert_query = """
                    INSERT INTO transactions (
                        trans_date_trans_time, cc_num, merchant, category, amt,
                        first, last, gender, street, city, state, zip,
                        lat, long, city_pop, job, dob, trans_num, unix_time,
                        merch_lat, merch_long, is_fraud
                    ) VALUES %s
                """
                execute_values(cursor, insert_query, batch)
                conn.commit()
                save_checkpoint(i, row.get('trans_num'))
                print(f"✅ Bulk loaded {records_loaded}/{num_records} records (final batch)")
            
            print(f"\n{'='*60}")
            print(f"🎉 BULK LOAD COMPLETE!")
            print(f"{'='*60}")
            print(f"📊 Total records loaded: {records_loaded}")
            print(f"📍 Final checkpoint: Line {i}")
            print(f"✅ Ready for streaming mode")
            print(f"{'='*60}\n")
            
    except FileNotFoundError:
        print(f"❌ Error: Data file not found at {DATA_FILE}.")
    except Exception as e:
        print(f"❌ An error occurred during bulk load: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if cursor:
            conn.commit()
            cursor.close()
        if conn:
            conn.close()
            print("✅ PostgreSQL connection closed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Fraud Detection Data Producer')
    parser.add_argument('--bulk-load', type=int, metavar='NUM_RECORDS',
                       help='Bulk load NUM_RECORDS records quickly (e.g., --bulk-load 50000)')
    
    args = parser.parse_args()
    
    if args.bulk_load:
        print(f"\n🚀 Running in BULK LOAD mode: {args.bulk_load} records")
        bulk_load_transactions(args.bulk_load)
    else:
        print(f"\n🔄 Running in STREAMING mode")
        simulate_real_time_stream()