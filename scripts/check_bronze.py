#!/usr/bin/env python3
import boto3
from botocore.client import Config

# MinIO configuration
s3 = boto3.client(
    's3',
    endpoint_url='http://minio:9000',
    aws_access_key_id='minio',
    aws_secret_access_key='minio123',
    config=Config(signature_version='s3v4')
)

try:
    # List objects in Bronze layer
    response = s3.list_objects_v2(
        Bucket='lakehouse',
        Prefix='bronze/transactions/'
    )
    
    if 'Contents' in response:
        print(f"Found {len(response['Contents'])} files in Bronze layer:")
        print("-" * 80)
        total_size = 0
        for obj in response['Contents']:
            size_mb = obj['Size'] / (1024 * 1024)
            print(f"  {obj['Key']:<60} {size_mb:>10.2f} MB")
            total_size += obj['Size']
        print("-" * 80)
        print(f"Total: {total_size / (1024 * 1024):.2f} MB")
    else:
        print("❌ Bronze layer is EMPTY - no files found!")
        print("\nChecking checkpoint location...")
        checkpoint_response = s3.list_objects_v2(
            Bucket='lakehouse',
            Prefix='checkpoints/bronze/'
        )
        if 'Contents' in checkpoint_response:
            print(f"✅ Checkpoint exists with {len(checkpoint_response['Contents'])} files")
        else:
            print("❌ No checkpoint found either")

except Exception as e:
    print(f"Error accessing MinIO: {e}")
