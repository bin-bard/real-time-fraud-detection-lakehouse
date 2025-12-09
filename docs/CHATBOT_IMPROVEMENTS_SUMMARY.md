# 🎯 Fraud Chatbot - Cải tiến hoàn chỉnh

## 📅 Ngày: 10/12/2025

## 🔄 Tổng quan thay đổi

Dự án chatbot đã được **tái cấu trúc hoàn toàn** từ monolithic `app/chatbot.py` (1251 dòng) thành kiến trúc modular với 15+ modules chuyên biệt.

---

## 📁 Cấu trúc mới

### Trước (❌ Monolithic)

```
fraud-chatbot/
├── Dockerfile
├── requirements.txt
└── app/
    └── chatbot.py  (1251 dòng - tất cả logic trong 1 file)
```

### Sau (✅ Modular)

```
fraud-chatbot/
├── Dockerfile
├── requirements.txt
├── .env.template
├── README_NEW_STRUCTURE.md
└── src/
    ├── main.py                   # Entry point (120 dòng)
    ├── components/               # UI Layer
    │   ├── sidebar.py            # Session management
    │   ├── chat_bubble.py        # Message rendering
    │   ├── forms.py              # Manual form & CSV upload
    │   └── analytics_charts.py   # Plotly charts
    ├── core/                     # Business Logic
    │   ├── agent.py              # LangChain ReAct Agent
    │   └── tools.py              # Agent Tools
    ├── database/                 # Data Layer
    │   ├── postgres.py           # Chat history
    │   └── trino.py              # Delta Lake
    └── utils/                    # Utilities
        ├── api_client.py         # FastAPI client
        └── formatting.py         # Helpers
```

---

## ✨ Tính năng mới

### 1. 🤖 LangChain ReAct Agent

**Trước:** Sử dụng if-else keywords để phân loại câu hỏi

```python
if "top" in question or "cao nhất" in question:
    # SQL query
elif "dự đoán" in question or "predict" in question:
    # Prediction
```

**Sau:** AI Agent tự động chọn tool phù hợp

```python
agent = create_react_agent(llm, tools=[QueryDatabase, PredictFraud])
result = agent.invoke({"input": question})
```

**Lợi ích:**

- ✅ Xử lý câu phức hợp: "Check $500 và so sánh fraud rate TX"
- ✅ Linh hoạt, không cần hard-code keywords
- ✅ Tự sửa lỗi SQL và retry

**Ví dụ:**

```
User: "Dự đoán $850 lúc 2h sáng ở merchant Walmart"

Agent:
  Thought: Cần dùng PredictFraud tool
  Action: PredictFraud
  Action Input: {"amt": 850, "hour": 2, "merchant": "Walmart"}
  Observation: [Kết quả prediction]
  Final Answer: Giao dịch này có xác suất gian lận 78%...
```

### 2. ✍️ Manual Prediction Form

**Vị trí:** Sidebar > Tools > Manual Prediction

**Tính năng:**

- Form nhập đầy đủ: amt, hour, distance_km, age, merchant, category
- Tự tính derived features (log_amount, hour_sin/cos...)
- Kết quả hiển thị ngay trong chat

**Use case:** Nhân viên vận hành cần check nhanh 1 giao dịch nghi ngờ

### 3. 📤 CSV Batch Upload

**Vị trí:** Sidebar > Tools > Batch Upload

**Tính năng:**

- Download template CSV
- Upload file → Batch predict
- Hiển thị summary: X/Y giao dịch fraud
- Download kết quả CSV

**Use case:** Check hàng loạt 100+ giao dịch từ Excel

### 4. 🔍 SQL Query Tracking

**Fix lỗi:** `chat_history.sql_query` luôn NULL

**Trước:**

```python
save_message(session_id, "assistant", answer)  # sql_query = NULL
```

**Sau:**

```python
sql_queries = extract_sql_queries(intermediate_steps)
save_message(session_id, "assistant", answer, sql_query="\n".join(sql_queries))
```

**Kết quả:**

- ✅ SQL queries được lưu vào DB
- ✅ Hiển thị trong chat: "🔍 SQL Query"
- ✅ Audit trail hoàn chỉnh

### 5. 💾 Fraud Predictions Storage

**Fix lỗi:** `fraud_predictions` table trống

**Nguyên nhân:**

1. Thiếu UNIQUE constraint → duplicate error
2. `save_prediction_to_db()` không được gọi đúng cách

**Giải pháp:**

**Database:**

```sql
-- Thêm UNIQUE constraint
ALTER TABLE fraud_predictions
ADD CONSTRAINT trans_num_unique UNIQUE (trans_num);
```

**FastAPI:**

```python
# ON CONFLICT UPDATE để tránh duplicate
INSERT INTO fraud_predictions (...)
VALUES (...)
ON CONFLICT (trans_num) DO UPDATE SET ...
```

**Kết quả:**

- ✅ Mọi prediction đều được lưu
- ✅ Không lỗi duplicate
- ✅ Query được: `SELECT * FROM fraud_predictions LIMIT 10`

---

## 🛠️ Thay đổi kỹ thuật

### Dependencies

**Thêm mới:**

```txt
langchain==0.1.20              # Agent framework
langchain-google-genai==1.0.3  # Gemini integration
tabulate==0.9.0                # Markdown tables
plotly==5.18.0                 # Charts
```

**Update:**

```txt
streamlit==1.31.0      (từ 1.29.0)
pandas==2.2.0          (từ 2.1.4)
sqlalchemy==2.0.25     (từ 2.0.23)
```

### Dockerfile

**Trước:**

```dockerfile
COPY app/ ./app/
CMD ["streamlit", "run", "app/chatbot.py", ...]
```

**Sau:**

```dockerfile
COPY src/ ./src/
CMD ["streamlit", "run", "src/main.py", ...]
```

### Docker Compose

**Trước:**

```yaml
volumes:
  - ./services/fraud-chatbot/app:/app/app
```

**Sau:**

```yaml
volumes:
  - ./services/fraud-chatbot/src:/app/src
```

---

## 📊 Database Migrations

### Migration 1: fraud_predictions

```sql
ALTER TABLE fraud_predictions
ADD CONSTRAINT trans_num_unique UNIQUE (trans_num);

CREATE INDEX idx_fraud_predictions_time
ON fraud_predictions(prediction_time DESC);
```

### Migration 2: chat_history

```sql
ALTER TABLE chat_history
ADD COLUMN IF NOT EXISTS sql_query TEXT;

CREATE INDEX idx_chat_history_session
ON chat_history(session_id, created_at);
```

**Chạy migrations:**

```powershell
.\scripts\run-migrations.ps1
```

---

## 🚀 Deployment

### Option 1: Script tự động

```powershell
.\scripts\deploy-chatbot.ps1

# Hoặc clean build
.\scripts\deploy-chatbot.ps1 -CleanBuild
```

### Option 2: Manual

```powershell
# 1. Run migrations
.\scripts\run-migrations.ps1

# 2. Rebuild chatbot
docker-compose up -d --build fraud-chatbot

# 3. Check logs
docker logs fraud-chatbot -f
```

---

## 🧪 Testing

### Test 1: SQL Analytics

```
Top 5 bang có fraud rate cao nhất
```

**Expected:**

- Agent dùng QueryDatabase
- SQL: `SELECT state, fraud_rate FROM state_summary ORDER BY fraud_rate DESC LIMIT 5`
- Kết quả hiển thị bảng markdown
- SQL lưu vào chat_history

### Test 2: Prediction

```
Dự đoán giao dịch $850 lúc 2h sáng
```

**Expected:**

- Agent dùng PredictFraud
- Kết quả: Fraud probability, risk level
- Lưu vào fraud_predictions

### Test 3: Complex Query

```
Check giao dịch $500 và so sánh với fraud rate trung bình của Texas
```

**Expected:**

- Agent dùng cả 2 tools
- Step 1: PredictFraud(amt=500)
- Step 2: QueryDatabase("SELECT AVG(...) WHERE state='TX'")
- Final Answer: So sánh 2 kết quả

### Test 4: Manual Form

1. Sidebar > Tools > Manual Prediction
2. Nhập: amt=1200, hour=14, distance_km=150
3. Click "Dự đoán"
   **Expected:** Kết quả hiện trong chat

### Test 5: Batch Upload

1. Sidebar > Tools > Batch Upload
2. Download template
3. Upload CSV với 3 giao dịch
4. Click "Batch Predict"
   **Expected:**

- Summary: 3 transactions processed
- Download kết quả CSV

### Test 6: Database Verification

```sql
-- Check SQL queries saved
SELECT session_id, sql_query
FROM chat_history
WHERE sql_query IS NOT NULL
LIMIT 5;

-- Check predictions saved
SELECT * FROM fraud_predictions
ORDER BY prediction_time DESC
LIMIT 10;
```

---

## 📈 Metrics

### Code Quality

- ✅ **Giảm coupling:** Từ 1 file → 15 modules
- ✅ **Single Responsibility:** Mỗi module 1 nhiệm vụ
- ✅ **Testability:** Dễ unit test từng module
- ✅ **Maintainability:** Sửa 1 chỗ không ảnh hưởng toàn bộ

### Performance

- ✅ **Agent caching:** LLM cached với @st.cache_resource
- ✅ **Pre-aggregated tables:** Ưu tiên state_summary, merchant_analysis
- ✅ **SQL indexing:** Indexes trên các columns quan trọng

### User Experience

- ✅ **Multi-modal input:** Chat + Form + CSV
- ✅ **Transparency:** Hiển thị SQL queries, thinking process
- ✅ **Error handling:** Graceful degradation khi API down

---

## 🐛 Known Issues & Solutions

### Issue 1: Import errors

**Lỗi:** `ModuleNotFoundError: No module named 'components'`

**Giải pháp:**

```python
# Thêm vào đầu mỗi file
import sys
import os
sys.path.append(os.path.dirname(__file__))
```

### Issue 2: Agent timeout

**Lỗi:** Agent mất >30s để trả lời

**Giải pháp:**

- Giảm `max_iterations` từ 10 → 5
- Dùng pre-aggregated tables
- Cache LLM responses

### Issue 3: SQL syntax errors

**Lỗi:** Trino syntax khác PostgreSQL

**Giải pháp:**

- Agent prompt có ví dụ Trino SQL
- Error handling: retry với corrected SQL

---

## 📚 Documentation

### Files mới

1. `README_NEW_STRUCTURE.md` - Hướng dẫn sử dụng
2. `.env.template` - Template environment variables
3. `scripts/deploy-chatbot.ps1` - Auto deployment
4. `scripts/run-migrations.ps1` - Database migrations
5. `database/migrations/*.sql` - Migration scripts

### Code documentation

- ✅ Docstrings cho mọi function
- ✅ Type hints đầy đủ
- ✅ Comments giải thích logic phức tạp

---

## 🎓 Lessons Learned

### 1. Modular > Monolithic

Tách code thành modules giúp:

- Debug nhanh hơn
- Reuse code dễ dàng
- Onboard dev mới nhanh

### 2. Agent > If-Else

LangChain Agent linh hoạt hơn nhiều so với keyword matching

### 3. Database Design

- UNIQUE constraints quan trọng
- Indexes cải thiện performance rõ rệt
- Migrations cần test kỹ trước khi deploy

### 4. User Experience

- Multi-modal input tăng productivity
- Transparency (hiển thị SQL, thinking) tăng trust
- Error messages phải clear và actionable

---

## 🔮 Future Enhancements

### Phase 2 (Tương lai)

1. **Memory:** Agent nhớ context từ câu hỏi trước
2. **Multi-language:** Support English
3. **Voice input:** Speech-to-text
4. **Charts:** Auto generate Plotly charts từ SQL results
5. **Export:** Export chat history as PDF
6. **Webhooks:** Alert khi detect high-risk transaction
7. **A/B Testing:** So sánh rule-based vs ML model

---

## ✅ Checklist triển khai

- [x] Tái cấu trúc code thành modules
- [x] Implement LangChain Agent
- [x] Tạo Manual Prediction Form
- [x] Tạo CSV Batch Upload
- [x] Fix SQL query tracking
- [x] Fix fraud_predictions storage
- [x] Update Dockerfile & docker-compose
- [x] Viết database migrations
- [x] Tạo deployment scripts
- [x] Viết documentation
- [ ] **Testing trên production** ← TIẾP THEO
- [ ] Monitoring & logging
- [ ] User training

---

## 📞 Support

Nếu gặp vấn đề:

1. Check logs: `docker logs fraud-chatbot -f`
2. Test connections: Sidebar > Test Trino
3. Clear cache: Sidebar > Clear Cache
4. Restart: `docker-compose restart fraud-chatbot`
5. Rebuild: `.\scripts\deploy-chatbot.ps1 -CleanBuild`

---

**Tác giả:** GitHub Copilot  
**Ngày:** 10/12/2025  
**Version:** 2.0.0
