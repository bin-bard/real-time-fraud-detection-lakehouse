import time
import random
import json

# Placeholder producer that prints simulated transactions

def generate_transaction():
    return {
        'transaction_id': random.randint(100000,999999),
        'amount': round(random.uniform(1,500),2),
        'is_fraud': random.choice([0,0,0,1])
    }

if __name__ == '__main__':
    while True:
        tx = generate_transaction()
        print(json.dumps(tx))
        time.sleep(1)
