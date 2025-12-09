# 🕵️ Fraud Detection Chatbot - Cấu trúc mới

## 📁 Cấu trúc thư mục

```
fraud-chatbot/
├── Dockerfile                    # Container config
├── requirements.txt              # Python dependencies
├── .env.template                 # Template cho env vars
└── src/                          # Source code chính
    ├── main.py                   # Entry point - Streamlit app
    ├── components/               # UI Components
    │   ├── sidebar.py            # Session management, tools
    │   ├── chat_bubble.py        # Message rendering
    │   ├── forms.py              # Manual form & CSV upload
    │   └── analytics_charts.py   # Plotly charts
    ├── core/                     # Business Logic
    │   ├── agent.py              # LangChain ReAct Agent
    │   └── tools.py              # Agent Tools (QueryDB, PredictFraud)
    ├── database/                 # Database connections
    │   ├── postgres.py           # Chat history storage
    │   └── trino.py              # Delta Lake queries
    └── utils/                    # Utilities
        ├── api_client.py         # FastAPI client
        └── formatting.py         # Format helpers
```

## 🚀 Tính năng mới

### ✅ LangChain ReAct Agent

- **Tự động chọn công cụ** phù hợp dựa trên câu hỏi
- 2 tools chính:
  - `QueryDatabase`: Query Trino Delta Lake
  - `PredictFraud`: Dự đoán fraud bằng ML model
- Xử lý được **câu hỏi phức hợp**: "Check $500 và so sánh với fraud rate TX"

### ✅ Manual Prediction Form

- Nhập thủ công thông tin giao dịch qua form
- Nhanh hơn chat cho nhân viên vận hành
- Trong sidebar: **Tools > Manual Prediction**

### ✅ CSV Batch Upload

- Upload file CSV để dự đoán hàng loạt
- Download template CSV mẫu
- Kết quả hiển thị summary + download CSV
- Trong sidebar: **Tools > Batch Upload**

### ✅ SQL Query Tracking

- **FIX**: Lưu SQL queries vào `chat_history.sql_query`
- Hiển thị SQL đã dùng trong chat
- Giúp debug và audit

### ✅ Fraud Predictions Storage

- **FIX**: Lưu tất cả predictions vào `fraud_predictions` table
- UNIQUE constraint trên `trans_num` tránh duplicate
- ON CONFLICT UPDATE để update nếu predict lại

## 🛠️ Setup & Deploy

### 1. Copy .env template

```bash
cp .env.template .env
# Sửa GOOGLE_API_KEY trong .env
```

### 2. Rebuild container

```bash
docker-compose up -d --build fraud-chatbot
```

### 3. Truy cập

- Chatbot UI: http://localhost:8501
- FastAPI: http://localhost:8000/docs

## 💬 Ví dụ sử dụng

### SQL Analytics

```
Top 5 bang có fraud rate cao nhất
```

### Prediction

```
Dự đoán giao dịch $850 lúc 2h sáng
```

### Câu phức hợp

```
Check giao dịch $500 và so sánh với fraud rate trung bình của Texas
```

→ Agent sẽ:

1. PredictFraud(amt=500)
2. QueryDatabase("SELECT AVG(fraud_rate) FROM state_summary WHERE state='TX'")
3. Kết hợp 2 kết quả

## 📊 Database Schema

### chat_history

```sql
CREATE TABLE chat_history (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(100),
    role VARCHAR(20),
    message TEXT,
    sql_query TEXT,  -- FIX: Lưu SQL query
    created_at TIMESTAMP
);
```

### fraud_predictions

```sql
CREATE TABLE fraud_predictions (
    id SERIAL PRIMARY KEY,
    trans_num VARCHAR(100) UNIQUE,  -- FIX: UNIQUE constraint
    prediction_score NUMERIC(5, 4),
    is_fraud_predicted SMALLINT,
    model_version VARCHAR(50),
    prediction_time TIMESTAMP
);
```

## 🔧 Troubleshooting

### Cache issues

Sidebar > Tools > **Clear Cache**

### Database connection

Sidebar > System Status > **Test Trino**

### Xem logs

```bash
docker logs fraud-chatbot -f
```

## 📝 Migration từ app/ sang src/

File cũ `app/chatbot.py` giờ được tách thành:

- `src/main.py` - Entry point
- `src/core/agent.py` - Agent logic
- `src/database/*.py` - DB connections
- `src/components/*.py` - UI components

Code cũ vẫn còn trong `app/` để tham khảo nếu cần.
