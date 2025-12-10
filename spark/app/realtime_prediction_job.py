"""
Real-Time Fraud Detection Streaming Job
Kafka CDC → Alert Service (Prediction + Slack)

Flow:
1. Read CDC events from Kafka (Debezium)
2. Parse transaction data
3. Call FastAPI /predict/raw for each transaction
4. Save prediction to fraud_predictions table
5. Send Slack alert for ALL fraud (LOW/MEDIUM/HIGH)

Note: Transactions are already inserted to PostgreSQL by data-producer
Alert service only handles prediction + alerting based on CDC events
"""

from pyspark.sql import SparkSession
from pyspark.sql.functions import from_json, col, current_timestamp
from pyspark.sql.types import StructType, StructField, StringType, DoubleType, IntegerType, TimestampType
import requests
import json
import logging
from math import radians, sin, cos, sqrt, atan2
from datetime import datetime
import os

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
KAFKA_BROKER = os.getenv("KAFKA_BROKER", "kafka:9092")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "postgres.public.transactions")
FRAUD_API_URL = os.getenv("FRAUD_API_URL", "http://fraud-detection-api:8000")
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")

# PostgreSQL config
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "postgres")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB = os.getenv("POSTGRES_DB", "frauddb")
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")

# Initialize Spark
logger.info("🔧 Initializing Spark Session...")
spark = SparkSession.builder \
    .appName("RealTimeFraudPrediction") \
    .config("spark.jars.packages", 
            "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0," +
            "org.postgresql:postgresql:42.7.1") \
    .getOrCreate()

spark.sparkContext.setLogLevel("WARN")
logger.info("✅ Spark Session initialized")

# Debezium CDC schema (after.value)
# NOTE: trans_date_trans_time from Debezium is BIGINT (microseconds since epoch)
transaction_schema = StructType([
    StructField("trans_date_trans_time", StringType()),  # Will convert from microseconds to timestamp
    StructField("cc_num", StringType()),  # Keep as String, will cast later
    StructField("merchant", StringType()),
    StructField("category", StringType()),
    StructField("amt", DoubleType()),
    StructField("first", StringType()),
    StructField("last", StringType()),
    StructField("gender", StringType()),
    StructField("street", StringType()),
    StructField("city", StringType()),
    StructField("state", StringType()),
    StructField("zip", IntegerType()),
    StructField("lat", DoubleType()),
    StructField("long", DoubleType()),
    StructField("city_pop", IntegerType()),
    StructField("job", StringType()),
    StructField("dob", IntegerType()),  # Debezium sends as integer (days since epoch)
    StructField("trans_num", StringType()),
    StructField("unix_time", IntegerType()),  # Changed from String to Integer
    StructField("merch_lat", DoubleType()),
    StructField("merch_long", DoubleType()),
    StructField("is_fraud", IntegerType())
])

def calculate_distance(lat1, lon1, lat2, lon2):
    """Haversine distance in km"""
    if not all([lat1, lon1, lat2, lon2]):
        return 10.0  # Default
    
    R = 6371  # Earth radius in km
    
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    
    return R * c

def calculate_age(dob_input):
    """Calculate age from DOB (int days or string)"""
    try:
        if isinstance(dob_input, int):
            # Debezium: days since 1970-01-01
            from datetime import date, timedelta
            dob = date(1970, 1, 1) + timedelta(days=dob_input)
        else:
            # String format
            dob = datetime.strptime(str(dob_input), "%Y-%m-%d")
        
        return (datetime.now().date() - dob).days // 365
    except:
        return 35  # Default

def send_slack_alert(alert_data):
    """
    Send alert to Slack for ALL fraud detections
    Risk level determines color: HIGH=🔴, MEDIUM=🟡, LOW=🟢
    """
    
    if not SLACK_WEBHOOK_URL:
        logger.warning("⚠️ SLACK_WEBHOOK_URL not configured, skipping alert")
        return False
    
    # Risk emoji
    risk_emoji_map = {
        "HIGH": "🔴",
        "MEDIUM": "🟡", 
        "LOW": "🟢"
    }
    risk_emoji = risk_emoji_map.get(alert_data['risk_level'], "⚪")
    
    # Color for Slack attachment
    color_map = {
        "HIGH": "danger",    # Red
        "MEDIUM": "warning", # Yellow
        "LOW": "#36a64f"     # Green
    }
    color = color_map.get(alert_data['risk_level'], "#808080")
    
    slack_payload = {
        "text": f"🚨 *FRAUD DETECTED* {risk_emoji}",
        "attachments": [
            {
                "color": color,
                "blocks": [
                    {
                        "type": "header",
                        "text": {
                            "type": "plain_text",
                            "text": f"{risk_emoji} Fraud Alert - {alert_data['risk_level']} Risk"
                        }
                    },
                    {
                        "type": "section",
                        "fields": [
                            {"type": "mrkdwn", "text": f"*Transaction ID:*\n`{alert_data['trans_num']}`"},
                            {"type": "mrkdwn", "text": f"*Amount:*\n${alert_data['amt']:.2f}"},
                            {"type": "mrkdwn", "text": f"*Customer:*\n{alert_data['customer']}"},
                            {"type": "mrkdwn", "text": f"*Merchant:*\n{alert_data['merchant']}"},
                            {"type": "mrkdwn", "text": f"*Fraud Probability:*\n{alert_data['fraud_probability']:.1%}"},
                            {"type": "mrkdwn", "text": f"*Risk Level:*\n{alert_data['risk_level']}"}
                        ]
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*📍 Location:*\n{alert_data.get('city', 'N/A')}, {alert_data.get('state', 'N/A')}"
                        }
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*🔎 Analysis:*\n{alert_data.get('explanation', 'No explanation available')}"
                        }
                    },
                    {
                        "type": "context",
                        "elements": [
                            {
                                "type": "mrkdwn",
                                "text": f"⏰ Detected at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                            }
                        ]
                    }
                ]
            }
        ]
    }
    
    try:
        response = requests.post(
            SLACK_WEBHOOK_URL,
            json=slack_payload,
            timeout=5
        )
        
        if response.status_code == 200:
            logger.info(f"✅ Slack alert sent: {alert_data['trans_num']} ({alert_data['risk_level']})")
            return True
        else:
            logger.error(f"❌ Slack alert failed: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Slack alert exception: {e}")
        return False

def save_prediction_to_db(trans_num, prediction_result):
    """Save prediction to fraud_predictions table"""
    import psycopg2
    
    try:
        conn = psycopg2.connect(
            host=POSTGRES_HOST,
            port=POSTGRES_PORT,
            database=POSTGRES_DB,
            user=POSTGRES_USER,
            password=POSTGRES_PASSWORD
        )
        
        cur = conn.cursor()
        
        # Check if prediction already exists
        cur.execute(
            "SELECT id FROM fraud_predictions WHERE trans_num = %s",
            (trans_num,)
        )
        
        if cur.fetchone():
            logger.info(f"⏭️  Prediction already exists for {trans_num}, skipping")
            cur.close()
            conn.close()
            return False
        
        # Insert new prediction
        cur.execute("""
            INSERT INTO fraud_predictions (
                trans_num, 
                prediction_score, 
                is_fraud_predicted,
                model_version,
                prediction_time
            ) VALUES (%s, %s, %s, %s, NOW())
        """, (
            trans_num,
            prediction_result['fraud_probability'],
            prediction_result['is_fraud_predicted'],
            prediction_result.get('model_version', 'unknown')
        ))
        
        conn.commit()
        cur.close()
        conn.close()
        
        logger.info(f"💾 Saved prediction to DB: {trans_num}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to save prediction for {trans_num}: {e}")
        return False

def process_batch(batch_df, batch_id):
    """
    Process micro-batch:
    1. Insert transactions to PostgreSQL
    2. Call FastAPI for predictions
    3. Save to fraud_predictions
    4. Send Slack alert for ALL fraud
    """
    
    if batch_df.isEmpty():
        logger.debug(f"Batch {batch_id}: Empty, skipping")
        return
    
    count = batch_df.count()
    logger.info(f"=" * 80)
    logger.info(f"🔄 Batch {batch_id}: Processing {count} transactions")
    logger.info(f"=" * 80)
    
    # Cast types to match PostgreSQL schema
    from pyspark.sql.functions import col as spark_col, expr, year, from_unixtime
    
    batch_df_casted = batch_df \
        .withColumn("trans_date_trans_time", 
                   from_unixtime(spark_col("trans_date_trans_time").cast("bigint") / 1000000).cast("timestamp")) \
        .withColumn("cc_num", spark_col("cc_num").cast("bigint")) \
        .withColumn("dob", expr("date_add('1970-01-01', dob)"))
    
    # Filter valid years (Sparkov dataset: 2019, plus test data: 2025)
    batch_df_casted = batch_df_casted.filter(
        year(spark_col("trans_date_trans_time")).between(2019, 2025)
    )
    
    filtered_count = batch_df_casted.count()
    
    # Note: Producer already inserts to PostgreSQL, so transactions exist
    # Alert service only processes CDC events for prediction + alerting
    # No need to insert to transactions table (already done by producer)
    
    logger.info(f"⚡ Batch {batch_id}: Processing {filtered_count} transactions from CDC events")
    
    # Process ALL transactions from CDC (no duplicate check needed)
    transactions_to_process = batch_df_casted
    new_count = filtered_count
    
    # 2. Process each transaction for prediction
    fraud_detected = 0
    predictions_saved = 0
    alerts_sent = 0
    
    for row in transactions_to_process.collect():
        trans_num = row['trans_num']
        
        try:
            # Calculate derived fields
            distance_km = calculate_distance(
                row['lat'], row['long'],
                row['merch_lat'], row['merch_long']
            )
            age = calculate_age(row['dob'])
            hour = row['trans_date_trans_time'].hour if row['trans_date_trans_time'] else 12
            day_of_week = row['trans_date_trans_time'].weekday() if row['trans_date_trans_time'] else 0
            
            # Prepare raw data for API
            raw_data = {
                "amt": float(row['amt']),
                "hour": hour,
                "distance_km": distance_km,
                "age": age,
                "gender": row['gender'],
                "merchant": row['merchant'],
                "category": row['category'],
                "day_of_week": day_of_week,
                "trans_num": trans_num
            }
            
            # Call FastAPI /predict/raw
            response = requests.post(
                f"{FRAUD_API_URL}/predict/raw",
                json=raw_data,
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                
                is_fraud = result['is_fraud_predicted']
                fraud_prob = result['fraud_probability']
                risk_level = result['risk_level']
                
                logger.info(
                    f"  {trans_num}: "
                    f"Fraud={'YES' if is_fraud else 'NO'} "
                    f"({fraud_prob:.1%}), "
                    f"Risk={risk_level}"
                )
                
                # 3. Save to fraud_predictions
                if save_prediction_to_db(trans_num, result):
                    predictions_saved += 1
                
                # 4. Send Slack alert for ALL fraud (không chỉ HIGH)
                if is_fraud == 1:
                    fraud_detected += 1
                    
                    alert_data = {
                        "trans_num": trans_num,
                        "amt": row['amt'],
                        "merchant": row['merchant'],
                        "customer": f"{row['first']} {row['last']}",
                        "city": row['city'],
                        "state": row['state'],
                        "fraud_probability": fraud_prob,
                        "risk_level": risk_level,
                        "explanation": result.get('feature_explanation', 'No explanation available')
                    }
                    
                    if send_slack_alert(alert_data):
                        alerts_sent += 1
                        logger.warning(f"  🚨 ALERT sent for {trans_num} ({risk_level} risk)")
                
            else:
                logger.error(f"  ❌ {trans_num}: API error {response.status_code}")
                
        except Exception as e:
            logger.error(f"  ❌ {trans_num}: Processing failed: {e}")
    
    # Batch summary
    logger.info(f"=" * 80)
    logger.info(f"✨ Batch {batch_id} Summary:")
    logger.info(f"  CDC events processed: {count}")
    logger.info(f"  Transactions processed: {new_count}")
    logger.info(f"  Fraud detected: {fraud_detected}")
    logger.info(f"  Predictions saved: {predictions_saved}")
    logger.info(f"  Slack alerts sent: {alerts_sent}")
    logger.info(f"=" * 80)

# Main streaming query
logger.info("✨ Starting Real-Time Fraud Detection Streaming...")
logger.info(f"📡 Kafka Broker: {KAFKA_BROKER}")
logger.info(f"📋 Kafka Topic: {KAFKA_TOPIC}")
logger.info(f"🔮 API Endpoint: {FRAUD_API_URL}")
logger.info(f"💬 Slack Alerts: {'Enabled' if SLACK_WEBHOOK_URL else 'Disabled'}")
logger.info(f"ℹ️ Alert Policy: ALL fraud detections (LOW/MEDIUM/HIGH)")
logger.info(f"⚙️ Offset Strategy: latest (only NEW messages after service start)")
logger.info("=" * 80)

# Read from Kafka
# Production mode: use "latest" to only process NEW messages after service starts
# Checkpoint tracks offset, so restart won't reprocess old data
df = spark.readStream \
    .format("kafka") \
    .option("kafka.bootstrap.servers", KAFKA_BROKER) \
    .option("subscribe", KAFKA_TOPIC) \
    .option("startingOffsets", "latest") \
    .option("failOnDataLoss", "false") \
    .load()

# Parse Debezium CDC format
transactions = df.selectExpr("CAST(value AS STRING)") \
    .select(from_json(col("value"), StructType([
        StructField("after", transaction_schema)
    ])).alias("data")) \
    .select("data.after.*") \
    .filter(col("trans_num").isNotNull())

# Start streaming with micro-batching
query = transactions.writeStream \
    .foreachBatch(process_batch) \
    .outputMode("append") \
    .option("checkpointLocation", "s3a://lakehouse/checkpoints/realtime-prediction") \
    .trigger(processingTime="10 seconds") \
    .start()

logger.info("✅ Streaming query started successfully")
logger.info("⏳ Waiting for Kafka events...")

query.awaitTermination()
