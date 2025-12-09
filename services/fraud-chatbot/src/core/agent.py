"""
LangChain Agent cho Fraud Detection
Sử dụng ReAct pattern để tự động chọn tools
"""

from langchain.agents import AgentExecutor, create_react_agent
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import PromptTemplate
from typing import Dict
import streamlit as st
import os

# Import tools
import sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from core.tools import create_database_tool, create_prediction_tool
from core.config import GEMINI_MODEL_NAME, GEMINI_MAX_RETRIES, GEMINI_REQUEST_TIMEOUT

@st.cache_resource
def get_fraud_detection_agent() -> AgentExecutor:
    """Tạo ReAct Agent với 2 tools: QueryDatabase và PredictFraud"""
    
    # LLM - Gemini với retry limit
    llm = ChatGoogleGenerativeAI(
        model=GEMINI_MODEL_NAME,  # Centralized config
        temperature=0,
        google_api_key=os.getenv("GOOGLE_API_KEY", ""),
        max_retries=GEMINI_MAX_RETRIES,
        request_timeout=GEMINI_REQUEST_TIMEOUT
    )
    
    # Tools (pass LLM to prediction tool for AI insights)
    tools = [
        create_database_tool(),
        create_prediction_tool(llm)
    ]
    
    # Prompt template (ReAct format) - TIẾNG VIỆT
    prompt = PromptTemplate.from_template("""
Bạn là chuyên gia phân tích gian lận tài chính với 2 công cụ mạnh mẽ:

1. **QueryDatabase**: Truy vấn Delta Lake để phân tích dữ liệu lịch sử
2. **PredictFraud**: Dự đoán giao dịch mới có gian lận không

TOOLS:
{tools}

TOOL NAMES: {tool_names}

---

**Hướng dẫn sử dụng:**

- Nếu câu hỏi về **dữ liệu lịch sử** (top X, fraud rate, trends, thông tin model...) → Dùng QueryDatabase
- Nếu câu hỏi về **giao dịch cụ thể** (dự đoán, kiểm tra...) → Dùng PredictFraud
- Câu hỏi **phức hợp** → Dùng cả 2 tools theo thứ tự logic
- Câu hỏi **tổng quát** về fraud (định nghĩa, pattern...) → Trả lời trực tiếp không cần tool

**Ví dụ câu phức hợp:**
"Check giao dịch $500 và so sánh với fraud rate trung bình của merchant đó"
→ Bước 1: PredictFraud(amt=500.0)
→ Bước 2: QueryDatabase("SELECT AVG(fraud_rate) FROM merchant_analysis WHERE merchant = '...'")

**Parsing user input cho PredictFraud:**
- "Dự đoán giao dịch $850 lúc 2h sáng" → PredictFraud(amt=850, hour=2)
- "Check giao dịch $1200 xa 150km" → PredictFraud(amt=1200, distance_km=150)
- **QUAN TRỌNG:** amt phải là số (int hoặc float), KHÔNG phải string "$850"
- Ví dụ ĐÚNG: PredictFraud(amt=850, hour=2)
- Ví dụ SAI: PredictFraud(amt="$850", hour="2h")

**Lưu ý quan trọng:**
- SQL queries phải hợp lệ Trino syntax
- Ưu tiên dùng bảng pre-aggregated (state_summary, merchant_analysis) để nhanh
- **Schema thường dùng:**
  * merchant_analysis: merchant, merchant_category, total_transactions, fraud_transactions, avg_amount, fraud_rate
  * state_summary: state, total_transactions, fraud_transactions, fraud_rate
  * fraud_predictions: trans_num, is_fraud_predicted, fraud_probability, model_version (thông tin model)
- Nếu query lỗi COLUMN_NOT_FOUND → Dùng DESCRIBE <table> để xem schema chính xác
- **FINAL ANSWER:**
  * Với PredictFraud: TRẢ NGUYÊN VĂN output từ tool (giữ nguyên format markdown với emoji, tables)
  * Với QueryDatabase: Tóm tắt ngắn gọn kèm insight
  * KHÔNG viết lại hay tóm tắt output của PredictFraud
- Format kết quả bằng TIẾNG VIỆT
- Với số tiền, dùng format: $XXX,XXX.XX
- Với phần trăm, dùng: XX.X%

---

**Format trả lời (ReAct):**

Thought: [Tôi cần làm gì?]
Action: [Tên tool]
Action Input: [JSON input hoặc tham số]
Observation: [Kết quả tool]
... (lặp lại nếu cần nhiều bước)
Thought: [Tôi đã có đủ thông tin]
Final Answer: [Câu trả lời đầy đủ bằng tiếng Việt, format đẹp]

---

**Câu hỏi:** {input}

{agent_scratchpad}
    """)
    
    # Create agent
    agent = create_react_agent(
        llm=llm,
        tools=tools,
        prompt=prompt
    )
    
    # Executor với error handling
    executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,
        handle_parsing_errors=True,
        max_iterations=15,  # Tăng lên để xử lý câu hỏi phức tạp và retry
        max_execution_time=60,  # Timeout 60s để tránh loop vô hạn
        return_intermediate_steps=True
    )
    
    return executor

def run_agent(question: str) -> Dict:
    """Chạy agent và trả về kết quả"""
    
    agent = get_fraud_detection_agent()
    
    try:
        # Run với timeout để tránh retry vô hạn
        import signal
        
        def timeout_handler(signum, frame):
            raise TimeoutError("Agent execution timeout")
        
        # Set timeout 90s (cho phép max 2 retries của Gemini)
        # signal.alarm(90)  # Chỉ work trên Unix
        
        result = agent.invoke({"input": question})
        
        # signal.alarm(0)  # Cancel timeout
        
        return {
            "success": True,
            "answer": result.get("output", ""),
            "intermediate_steps": result.get("intermediate_steps", []),
            "sql_queries": extract_sql_queries(result.get("intermediate_steps", []))
        }
    except TimeoutError:
        return {
            "success": False,
            "error": "⏱️ Request timeout sau 90s. Có thể Gemini API đang quá tải."
        }
    except Exception as e:
        error_msg = str(e)
        
        # Check for quota exceeded error
        if "429" in error_msg or "quota" in error_msg.lower() or "ResourceExhausted" in error_msg:
            return {
                "success": False,
                "error": "⚠️ Gemini API quota exceeded (20 requests/day limit). Vui lòng thử lại sau vài phút hoặc upgrade plan tại https://ai.google.dev/pricing"
            }
        
        return {
            "success": False,
            "error": error_msg
        }

def extract_sql_queries(steps) -> list:
    """Trích xuất SQL queries từ intermediate steps"""
    queries = []
    
    for step in steps:
        if isinstance(step, tuple) and len(step) >= 2:
            action, observation = step
            
            # Check if tool was QueryDatabase
            if hasattr(action, 'tool') and action.tool == 'QueryDatabase':
                if hasattr(action, 'tool_input'):
                    # Tool input có thể là dict hoặc string
                    tool_input = action.tool_input
                    if isinstance(tool_input, dict):
                        sql = tool_input.get('sql_query', '')
                    else:
                        sql = str(tool_input)
                    
                    if sql:
                        queries.append(sql)
    
    return queries
