FROM python:3.9-slim

RUN pip install minio boto3

WORKDIR /app
COPY setup_minio.py .

CMD ["python", "setup_minio.py"]