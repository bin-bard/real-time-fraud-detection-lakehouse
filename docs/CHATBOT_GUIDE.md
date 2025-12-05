# 🤖 Hướng dẫn sử dụng Fraud Detection Chatbot

## Tổng quan

Chatbot này có thể trả lời **3 loại câu hỏi**:

1. **📊 SQL Analytics** - Phân tích dữ liệu từ Trino Gold Layer
2. **🔮 Fraud Prediction** - Dự đoán gian lận giao dịch mới
3. **💬 General Knowledge** - Câu hỏi tổng quát về fraud detection

---

## 1. SQL Analytics (Phân tích dữ liệu)

### Ví dụ câu hỏi:

```
- Có bao nhiêu giao dịch gian lận hôm nay?
- Top 5 bang có tỷ lệ gian lận cao nhất?
- Merchant nào nguy hiểm nhất?
- Phân tích fraud patterns theo amount bin
- Tổng số tiền bị gian lận tuần này?
- Hiển thị fraud rate theo từng giờ
- Category nào rủi ro nhất?
```

### Chatbot sẽ:

1. Hiểu câu hỏi bằng ngôn ngữ tự nhiên (tiếng Việt hoặc tiếng Anh)
2. Tự động tạo SQL query từ Trino database
3. Thực thi và trả về kết quả với giải thích
4. Hiển thị SQL query đã dùng (trong expander "🔍 SQL Query")

---

## 2. Fraud Prediction (Dự đoán gian lận)

### Ví dụ câu hỏi:

```
- Dự đoán giao dịch $850 vào lúc 2h sáng
- Check giao dịch $1200 xa 150km
- Phân tích giao dịch $50 lúc 14h, category shopping_net
- Đánh giá giao dịch $300 merchant ABC, 100km
```

### Chatbot sẽ:

1. Trích xuất thông tin giao dịch từ câu hỏi (số tiền, giờ, khoảng cách...)
2. Gọi FastAPI `/predict/explained` với model ML
3. Trả về kết quả dự đoán:
   - ✅ HỢP LỆ hoặc ⚠️ GIAN LẬN
   - Xác suất gian lận (%)
   - Risk level: 🟢 LOW / 🟡 MEDIUM / 🔴 HIGH
   - Giải thích chi tiết bằng LLM (Gemini)

### Thông tin bổ sung cần thiết:

**Bắt buộc:**

- `amt`: Số tiền giao dịch (USD)

**Tùy chọn (càng nhiều càng chính xác):**

- `hour`: Giờ giao dịch (0-23)
- `distance_km`: Khoảng cách từ địa chỉ khách hàng
- `merchant`: Tên merchant
- `category`: Loại giao dịch (shopping_net, grocery_pos, gas_transport...)
- `age`: Tuổi khách hàng

### Xem thông tin model:

```
- Xem thông tin model hiện tại
- Model info
- Model metrics
```

### Xem lịch sử predictions:

```
- Lịch sử predictions gần đây
- Prediction history
- 10 predictions mới nhất
```

---

## 3. General Knowledge (Câu hỏi tổng quát)

### Ví dụ câu hỏi:

```
- Gian lận tài chính là gì?
- Các loại fraud phổ biến?
- Amount bin là gì?
- Time period có những khung giờ nào?
- Làm sao phát hiện gian lận?
```

### Chatbot sẽ:

- Trả lời ngắn gọn dựa trên kiến thức tổng quát
- Sau đó gợi ý câu hỏi về fraud detection để tận dụng database

---

## Ví dụ Session hoàn chỉnh

### 📊 Analytics

**User:** "Top 5 bang có tỷ lệ gian lận cao nhất"

**Bot:**

```
Dựa trên dữ liệu phân tích, đây là top 5 bang:

1. New York - Fraud rate: 5.2%
2. California - Fraud rate: 4.8%
3. Texas - Fraud rate: 4.1%
...

🔍 SQL Query:
SELECT state, fraud_rate
FROM state_summary
ORDER BY fraud_rate DESC
LIMIT 5
```

---

### 🔮 Prediction

**User:** "Dự đoán giao dịch $1500 vào lúc 3h sáng xa 200km"

**Bot:**

```
🔴 Kết quả Dự đoán

Kết luận: ⚠️ GIAN LẬN
Xác suất gian lận: 92.5%
Risk Level: HIGH
Model: mlflow_v2.1

---

Giao dịch này có xác suất gian lận rất cao (92.5%) và model đã phân loại là GIAN LẬN.

Các yếu tố rủi ro chính:
1. Số tiền rất lớn ($1500) - thuộc Bin 5 có fraud rate 32%
2. Khoảng cách bất thường (200km) - xa địa chỉ khách hàng
3. Thời điểm nguy hiểm: 3h sáng (đêm khuya)

Khuyến nghị:
🚫 TỪ CHỐI giao dịch và liên hệ khách hàng xác minh.

📊 Chi tiết kỹ thuật:
- Số tiền: $1500.00
- Khoảng cách: 200.0km
- Thời gian: 3h, ngày thường
```

---

### 💬 General

**User:** "Amount bin là gì?"

**Bot:**

```
Amount bin là cách chia giao dịch thành 5 khoảng giá trị:

- Bin 1: $0 - $50 (giao dịch nhỏ, fraud rate ~0.24%)
- Bin 2: $50 - $150 (fraud rate ~0.52%)
- Bin 3: $150 - $300 (fraud rate ~0.04%)
- Bin 4: $300 - $500 (fraud rate ~1.59%)
- Bin 5: >$500 (giao dịch lớn, fraud rate CAO NHẤT 32.26%)

Tôi chuyên về phân tích gian lận. Bạn có muốn hỏi về fraud patterns
hoặc phân tích merchant rủi ro không? 😊
```

---

## Tính năng nâng cao

### 1. Quản lý Sessions

- Tạo chat mới: Click "➕ Chat mới"
- Load chat cũ: Click vào session trong sidebar
- Xóa chat: Click "🗑️" bên cạnh session

### 2. Test Connection

- Click "🔌 Test Connection" để kiểm tra kết nối Trino
- Hiển thị số lượng records trong fact_transactions

### 3. AI Thinking Process

- Mở rộng "🧠 AI Thinking Process" để xem cách AI suy luận
- Hữu ích cho debugging và hiểu cách agent hoạt động

### 4. Clear Cache

- Click "🗑️ Clear Cache" nếu gặp lỗi connection
- Sau đó nhấn Ctrl+R để reload

---

## Troubleshooting

### Lỗi: "API không khả dụng"

```bash
# Kiểm tra fraud-detection-api đang chạy
docker ps | grep fraud-detection-api

# Xem logs
docker logs fraud-detection-api --tail 50

# Restart
docker-compose restart fraud-detection-api
```

### Lỗi: "Model chưa train"

- API sẽ tự động fallback sang rule-based prediction
- Để train model, chạy notebook: `notebooks/02-model-training-experiment.ipynb`

### Lỗi: "GOOGLE_API_KEY chưa cấu hình"

```bash
# Thêm vào .env file
echo "GOOGLE_API_KEY=AIzaSy..." >> .env

# Restart chatbot
docker-compose restart fraud-chatbot
```

---

## Tips & Best Practices

### 📊 SQL Analytics

- Dùng ngôn ngữ tự nhiên, không cần biết SQL
- Hỏi cụ thể: "Top 5" thay vì "Những bang nào"
- Có thể hỏi theo tiếng Việt hoặc tiếng Anh

### 🔮 Prediction

- Cung cấp càng nhiều thông tin càng chính xác
- Bắt buộc có số tiền (`amt`)
- Thêm giờ + khoảng cách sẽ tăng độ chính xác
- Chatbot tự động extract thông tin từ câu hỏi

### 💬 General

- Chatbot vẫn trả lời được câu ngoài lề
- Nhưng sẽ gợi ý quay về fraud detection
- Tận dụng database để có câu trả lời chính xác hơn

---

## API Endpoints (cho developers)

### Fraud Detection API

```bash
# Health check
curl http://localhost:8000/health

# Model info
curl http://localhost:8000/model/info

# Predict (cơ bản)
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{...transaction_features...}'

# Predict với giải thích LLM
curl -X POST http://localhost:8000/predict/explained \
  -H "Content-Type: application/json" \
  -d '{...transaction_features...}'

# Lịch sử predictions
curl http://localhost:8000/predictions/history?limit=10

# Reload model
curl -X POST http://localhost:8000/model/reload
```

### Chatbot UI

```
http://localhost:8501
```

---

## Kiến trúc

```
┌─────────────┐
│   User      │
│  Question   │
└─────┬───────┘
      │
      ▼
┌─────────────────────────────────┐
│  Chatbot (Streamlit + Gemini)  │
│  - Phân loại câu hỏi            │
│  - Extract transaction info     │
│  - Route to appropriate handler │
└─────┬───────────┬───────────────┘
      │           │
      │           ▼
      │     ┌──────────────────┐
      │     │  FastAPI + ML    │
      │     │  - Load model    │
      │     │  - Predict       │
      │     │  - Explain (LLM) │
      │     └────────┬─────────┘
      │              │
      ▼              ▼
┌──────────┐   ┌──────────────┐
│  Trino   │   │  PostgreSQL  │
│  (Gold)  │   │  (Predictions│
│          │   │   + History) │
└──────────┘   └──────────────┘
```

---

## Tài liệu tham khảo

- **Database Schema:** `docs/PROJECT_SPECIFICATION.md`
- **Model Training:** `notebooks/02-model-training-experiment.ipynb`
- **API Docs:** http://localhost:8000/docs (FastAPI Swagger UI)
- **Troubleshooting:** `docs/TROUBLESHOOTING.md`

---

## Support

Nếu gặp vấn đề:

1. Kiểm tra logs: `docker logs fraud-chatbot --tail 50`
2. Test connection trong sidebar
3. Clear cache và reload
4. Xem `docs/TROUBLESHOOTING.md`
