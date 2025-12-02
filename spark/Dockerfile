# Custom Spark image with ML libraries
FROM apache/spark:3.4.1

# Switch to root to install packages
USER root

# Install netcat for healthcheck and Python ML dependencies
RUN apt-get update && apt-get install -y netcat-openbsd && \
    rm -rf /var/lib/apt/lists/* && \
    pip install --no-cache-dir \
    numpy==1.24.3 \
    pandas==2.0.3 \
    scikit-learn==1.3.0 \
    mlflow==2.8.0 \
    boto3==1.28.85 \
    psycopg2-binary==2.9.9

# Create Ivy cache directory with proper permissions
RUN mkdir -p /home/spark/.ivy2/cache && \
    mkdir -p /home/spark/.ivy2/jars && \
    chown -R 185:185 /home/spark/.ivy2 && \
    chmod -R 775 /home/spark/.ivy2

# Switch back to spark user
USER 185

# Set working directory
WORKDIR /opt/spark/work-dir
