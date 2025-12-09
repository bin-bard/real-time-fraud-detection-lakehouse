"""
Centralized Configuration
Quản lý tất cả constants và configs ở 1 nơi
"""

import os

# ==================== GEMINI CONFIGURATION ====================
# Chỉ cần đổi MODEL_NAME ở đây, tất cả modules sẽ tự động update
GEMINI_MODEL_NAME = os.getenv("GEMINI_MODEL_NAME", "gemini-2.5-flash-lite")
GEMINI_API_KEY = os.getenv("GOOGLE_API_KEY", "")
GEMINI_MAX_RETRIES = int(os.getenv("GEMINI_MAX_RETRIES", "2"))
GEMINI_REQUEST_TIMEOUT = int(os.getenv("GEMINI_REQUEST_TIMEOUT", "30"))
GEMINI_TEST_TIMEOUT = int(os.getenv("GEMINI_TEST_TIMEOUT", "10"))

# Available Gemini models (for reference)
GEMINI_MODELS = {
    "flash-lite": "gemini-2.5-flash-lite",  # Fast, cheap, 20 requests/day free tier
    "flash": "gemini-2.0-flash-exp",        # Balanced, experimental
    "pro": "gemini-1.5-pro",                # Most capable, slower
}

# ==================== API CONFIGURATION ====================
FRAUD_API_URL = os.getenv("FRAUD_API_URL", "http://fraud-detection-api:8000")
TRINO_API_URL = os.getenv("TRINO_API_URL", "http://trino:8080")

# ==================== DATABASE CONFIGURATION ====================
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "postgres")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB = os.getenv("POSTGRES_DB", "frauddb")
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")

# ==================== STREAMLIT CONFIGURATION ====================
PAGE_TITLE = "🛡️ Fraud Detection Assistant"
PAGE_ICON = "🛡️"
LAYOUT = "wide"

# ==================== AGENT CONFIGURATION ====================
AGENT_SYSTEM_PROMPT = """Bạn là trợ lý phân tích gian lận thông minh. 
Hỗ trợ tiếng Việt và English.

Nhiệm vụ:
- Trả lời câu hỏi về dữ liệu giao dịch
- Dự đoán gian lận cho giao dịch mới
- Giải thích kết quả một cách dễ hiểu

Luôn sử dụng tools khi cần thiết."""

# ==================== FEATURE ENGINEERING CONFIGURATION ====================
# TransactionFeatures có 20 fields, model dùng 15
FEATURE_COUNT_TOTAL = 20
FEATURE_COUNT_USED = 15
USER_INPUT_COUNT = 7  # amt, hour, distance_km, age, day_of_week, merchant, category
