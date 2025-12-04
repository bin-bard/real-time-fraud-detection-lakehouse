FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY producer.py .
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

# Mặc định: Streaming mode (chạy tự động khi start container)
# Để vào idle mode: set environment MODE=idle trong docker-compose.yml
ENTRYPOINT ["/app/entrypoint.sh"]
CMD []