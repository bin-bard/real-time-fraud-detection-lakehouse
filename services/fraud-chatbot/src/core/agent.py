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

@st.cache_resource
def get_fraud_detection_agent() -> AgentExecutor:
    """Tạo ReAct Agent với 2 tools: QueryDatabase và PredictFraud"""
    
    # LLM - Gemini
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash-lite",
        temperature=0,
        google_api_key=os.getenv("GOOGLE_API_KEY", ""),
        convert_system_message_to_human=True
    )
    
    # Tools
    tools = [
        create_database_tool(),
        create_prediction_tool()
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

- Nếu câu hỏi về **dữ liệu lịch sử** (top X, fraud rate, trends...) → Dùng QueryDatabase
- Nếu câu hỏi về **giao dịch cụ thể** (dự đoán, kiểm tra...) → Dùng PredictFraud
- Câu hỏi **phức hợp** → Dùng cả 2 tools theo thứ tự logic
- Câu hỏi **tổng quát** về fraud (định nghĩa, pattern...) → Trả lời trực tiếp không cần tool

**Ví dụ câu phức hợp:**
"Check giao dịch $500 và so sánh với fraud rate trung bình của merchant đó"
→ Bước 1: PredictFraud(amt=500)
→ Bước 2: QueryDatabase("SELECT AVG(fraud_rate) FROM merchant_analysis WHERE merchant = '...'")

**Lưu ý quan trọng:**
- SQL queries phải hợp lệ Trino syntax
- Ưu tiên dùng bảng pre-aggregated (state_summary, merchant_analysis) để nhanh
- Format kết quả bằng TIẾNG VIỆT, dễ đọc
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
        max_iterations=5,
        return_intermediate_steps=True
    )
    
    return executor

def run_agent(question: str) -> Dict:
    """Chạy agent và trả về kết quả"""
    
    agent = get_fraud_detection_agent()
    
    try:
        result = agent.invoke({"input": question})
        
        return {
            "success": True,
            "answer": result.get("output", ""),
            "intermediate_steps": result.get("intermediate_steps", []),
            "sql_queries": extract_sql_queries(result.get("intermediate_steps", []))
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
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
