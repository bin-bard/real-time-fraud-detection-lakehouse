# Custom Spark image with ML libraries
FROM apache/spark:3.4.1

# Switch to root to install packages
USER root

# Install Python ML dependencies
RUN pip install --no-cache-dir \
    numpy==1.24.3 \
    pandas==2.0.3 \
    scikit-learn==1.3.0 \
    mlflow==2.8.0 \
    boto3==1.28.85 \
    psycopg2-binary==2.9.9

# Switch back to spark user
USER 185

# Set working directory
WORKDIR /opt/spark/work-dir
