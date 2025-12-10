"""
Fraud Detection Chatbot - Main Application
Sử dụng LangChain Agent với ReAct pattern
"""

import streamlit as st
from datetime import datetime
import uuid
import sys
import os

# Add src to path
sys.path.append(os.path.dirname(__file__))

# Import modules
from components.sidebar import render_sidebar
from components.chat_bubble import render_message, render_thinking_process
from components.forms import ManualPredictionForm
from components.prediction_result import get_ai_insight, format_prediction_message
from core.agent import run_agent
from database.postgres import init_chat_history_table, save_message, load_chat_history
from utils.formatting import format_currency, format_percentage

def init_session_state():
    """Khởi tạo session state"""
    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())
    
    if "messages" not in st.session_state:
        st.session_state.messages = []

def new_chat_session():
    """Tạo chat mới"""
    st.session_state.session_id = str(uuid.uuid4())
    st.session_state.messages = []
    return st.session_state.session_id

def load_session(session_id: str):
    """Load session cũ"""
    st.session_state.session_id = session_id
    st.session_state.messages = load_chat_history(session_id)

def main():
    """Main application"""
    
    st.set_page_config(
        page_title="Fraud Detection Chatbot",
        page_icon="🕵️",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Initialize
    init_session_state()
    
    # Initialize database
    try:
        init_chat_history_table()
    except Exception as e:
        st.error(f"❌ Lỗi khởi tạo database: {str(e)}")
    
    # Sidebar
    new_session = render_sidebar(
        session_id=st.session_state.session_id,
        on_new_chat=new_chat_session,
        on_load_session=load_session
    )
    
    if new_session:
        st.rerun()
    
    # Main chat area
    st.title("💬 Fraud Detection Chatbot")
    st.caption(f"Session: `{st.session_state.session_id[:8]}...`")
    
    # Display messages
    for msg in st.session_state.messages:
        render_message(msg)
    
    # Check for manual prediction result (từ sidebar form)
    if hasattr(st.session_state, 'manual_prediction_result'):
        result = st.session_state.manual_prediction_result
        
        # Generate AI insight using component
        with st.spinner("🤖 Đang phân tích kết quả..."):
            ai_insight = get_ai_insight(result)
        
        # Format message using shared component
        formatted_content = format_prediction_message(result, ai_insight)
        
        prediction_msg = {
            "role": "assistant",
            "content": formatted_content,
            "prediction_data": result
        }
        
        st.session_state.messages.append(prediction_msg)
        save_message(st.session_state.session_id, "assistant", prediction_msg["content"])
        
        # Clear result
        del st.session_state.manual_prediction_result
        st.rerun()
    
    # Chat input
    if prompt := st.chat_input("Hỏi gì đó về fraud detection..."):
        
        # Add user message
        user_msg = {
            "role": "user",
            "content": prompt
        }
        
        st.session_state.messages.append(user_msg)
        save_message(st.session_state.session_id, "user", prompt)
        
        # Display user message
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Get AI response với Agent
        with st.chat_message("assistant"):
            with st.spinner("🤔 Agent đang suy nghĩ..."):
                
                # Run agent
                result = run_agent(prompt)
                
                if result["success"]:
                    answer = result["answer"]
                    sql_queries = result.get("sql_queries", [])
                    intermediate_steps = result.get("intermediate_steps", [])
                    
                    # Display answer
                    st.markdown(answer)
                    
                    # Show SQL queries nếu có
                    if sql_queries:
                        with st.expander("🔍 SQL Queries Used"):
                            for i, sql in enumerate(sql_queries, 1):
                                st.code(sql, language="sql")
                    
                    # Show thinking process
                    render_thinking_process(intermediate_steps)
                    
                    # Save to database VỚI SQL
                    sql_query = "\n\n".join(sql_queries) if sql_queries else None
                    
                    assistant_msg = {
                        "role": "assistant",
                        "content": answer,
                        "sql_query": sql_query  # ← FIX: Lưu SQL
                    }
                    
                    st.session_state.messages.append(assistant_msg)
                    save_message(st.session_state.session_id, "assistant", answer, sql_query)
                
                else:
                    error_msg = f"❌ Lỗi: {result['error']}"
                    st.error(error_msg)
                    
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": error_msg
                    })
                    save_message(st.session_state.session_id, "assistant", error_msg)

if __name__ == "__main__":
    main()
