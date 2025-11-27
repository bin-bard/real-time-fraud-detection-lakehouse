#!/usr/bin/env python3
"""
Script để khởi tạo MinIO buckets và folder structure cho Data Lakehouse
"""
from minio import Minio
from minio.error import S3Error
import time
import sys

def setup_minio():
    print("🚀 Setting up MinIO for Data Lakehouse...")
    
    # Kết nối đến MinIO (từ container thì dùng hostname 'minio')
    minio_endpoint = "minio:9000"  # Trong Docker network
    
    client = Minio(
        minio_endpoint,
        access_key="minio",
        secret_key="minio123",
        secure=False
    )
    
    bucket_name = "lakehouse"
    
    try:
        # Kiểm tra và tạo bucket
        if not client.bucket_exists(bucket_name):
            client.make_bucket(bucket_name)
            print(f"✅ Bucket '{bucket_name}' created successfully.")
        else:
            print(f"✅ Bucket '{bucket_name}' already exists.")
            
        # Tạo folder structure cho Medallion Architecture
        folders = [
            "bronze/transactions/.keep",
            "silver/transactions/.keep", 
            "silver/features/.keep",
            "gold/aggregated/.keep",
            "gold/reports/.keep",
            "checkpoints/bronze/.keep",
            "checkpoints/silver/.keep",
            "checkpoints/gold/.keep",
            "models/fraud_detection/.keep",
            "models/experiments/.keep"
        ]
        
        print(f"📁 Creating folder structure...")
        for file_path in folders:
            try:
                # Tạo file .keep để tạo folder structure  
                from io import BytesIO
                keep_content = BytesIO(b"# This file keeps the folder structure\n")
                client.put_object(bucket_name, file_path, keep_content, keep_content.getbuffer().nbytes)
                print(f"   ✅ {file_path}")
            except Exception as e:
                print(f"   ⚠️  {file_path} - {str(e)}")
                
        print(f"\n🎉 MinIO setup completed successfully!")
        print(f"📊 Data Lakehouse structure:")
        print(f"   📦 Bronze Layer: s3a://lakehouse/bronze/")
        print(f"   🥈 Silver Layer: s3a://lakehouse/silver/")
        print(f"   🥇 Gold Layer:   s3a://lakehouse/gold/")
        print(f"   🚀 Models:       s3a://lakehouse/models/")
        
        return True
            
    except S3Error as e:
        print(f"❌ MinIO Error: {e}")
        return False
    except Exception as e:
        print(f"❌ General Error: {e}")
        return False

def wait_for_minio(max_retries=30, delay=2):
    """Đợi MinIO khởi động"""
    print("⏳ Waiting for MinIO to be ready...")
    
    client = Minio(
        "minio:9000",  # Trong Docker network
        access_key="minio", 
        secret_key="minio123",
        secure=False
    )
    
    for i in range(max_retries):
        try:
            # Thử list buckets để test connection
            list(client.list_buckets())
            print("✅ MinIO is ready!")
            return True
        except Exception as e:
            print(f"   Attempt {i+1}/{max_retries}: {str(e)[:50]}...")
            time.sleep(delay)
    
    print("❌ MinIO is not responding after maximum retries")
    return False

if __name__ == "__main__":
    print("🔧 MinIO Data Lakehouse Setup Script")
    print("=" * 50)
    
    # Đợi MinIO khởi động
    if not wait_for_minio():
        sys.exit(1)
    
    # Setup buckets và folders
    if setup_minio():
        print("\n🌟 You can now access MinIO at:")
        print("   🌐 Web UI: http://localhost:9001")
        print("   🔑 Username: minio")
        print("   🔑 Password: minio123")
        sys.exit(0)
    else:
        sys.exit(1)