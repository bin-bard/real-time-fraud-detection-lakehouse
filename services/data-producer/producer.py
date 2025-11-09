import csv
import json
import time
from kafka import KafkaProducer
import os

# --- Cấu hình ---
KAFKA_BROKER = os.environ.get("KAFKA_BROKER", "kafka:9092")
KAFKA_TOPIC = "credit_card_transactions"
DATA_FILE = "/data/creditcard.csv"
# Hệ số co giãn thời gian. Ví dụ: 0.01 nghĩa là 1 giây trong dữ liệu gốc = 0.01 giây trong mô phỏng.
# Điều này giúp chạy hết bộ dữ liệu 2 ngày trong vài giờ thay vì 2 ngày thật.
TIME_SCALING_FACTOR = 0.01 

# --- Khởi tạo Kafka Producer ---
producer = None
while producer is None:
    try:
        producer = KafkaProducer(
            bootstrap_servers=[KAFKA_BROKER],
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        print("Kafka Producer connected successfully!")
    except Exception as e:
        print(f"Could not connect to Kafka, retrying in 5 seconds... Error: {e}")
        time.sleep(5)

# --- Đọc và gửi dữ liệu theo thời gian ---
def simulate_real_time_stream():
    print(f"Simulating real-time stream from {DATA_FILE}...")
    try:
        with open(DATA_FILE, 'r') as file:
            reader = csv.DictReader(file)
            last_transaction_time = 0
            
            # Đọc dòng đầu tiên để khởi tạo thời gian
            first_row = next(reader)
            last_transaction_time = float(first_row['Time'])
            
            # Xử lý và gửi dòng đầu tiên
            send_transaction(1, first_row)

            # Xử lý các dòng còn lại
            for i, row in enumerate(reader, start=2):
                current_transaction_time = float(row['Time'])
                
                # Tính toán thời gian chờ
                time_diff = current_transaction_time - last_transaction_time
                wait_time = time_diff * TIME_SCALING_FACTOR
                
                if wait_time > 0:
                    time.sleep(wait_time)
                
                # Gửi giao dịch
                send_transaction(i, row)
                
                last_transaction_time = current_transaction_time

    except FileNotFoundError:
        print(f"Error: Data file not found at {DATA_FILE}.")
    except Exception as e:
        print(f"An error occurred during simulation: {e}")
    finally:
        if producer:
            producer.flush()
            producer.close()
            print("Kafka producer closed.")

def send_transaction(index, row_data):
    """Helper function to process and send a single transaction."""
    try:
        # Chuyển đổi kiểu dữ liệu
        processed_row = {key: float(value) for key, value in row_data.items()}
        
        # Gửi message
        producer.send(KAFKA_TOPIC, value=processed_row)
        print(f"Sent message #{index} | Time: {processed_row['Time']}")
    except (ValueError, TypeError):
        print(f"Skipping row #{index} due to data conversion error.")
    except Exception as e:
        print(f"Error sending message #{index}: {e}")

if __name__ == "__main__":
    simulate_real_time_stream()