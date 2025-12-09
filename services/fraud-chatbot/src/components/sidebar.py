"""
Sidebar Component
Session management, tools, và system status
"""

import streamlit as st
from typing import Optional

# Import từ modules khác
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from utils.api_client import get_fraud_api_status
from database.trino import test_trino_connection
from database.postgres import get_all_sessions, delete_session
from components.forms import ManualPredictionForm, CSVBatchUploader

def render_sidebar(session_id: str, on_new_chat, on_load_session) -> Optional[str]:
    """Render sidebar với session management và tools"""
    
    with st.sidebar:
        st.title("🕵️ Fraud Chatbot")
        
        # API Status - Compact
        render_api_status()
        
        # Session Management
        new_session = render_session_manager(session_id, on_new_chat, on_load_session)
        
        # Tools
        render_tools()
        
        # Examples
        render_examples()
        
        return new_session

def render_api_status():
    """Hiển thị trạng thái API và connections - Compact layout"""
    
    with st.expander("⚙️ System Status", expanded=True):
        # Gemini API
        gemini_key = os.getenv("GOOGLE_API_KEY", "")
        if gemini_key and len(gemini_key) > 20:
            st.success(f"✅ Gemini ({gemini_key[:8]}...)")
        else:
            st.error("❌ Gemini API chưa config")
        
        # ML Model
        api_status = get_fraud_api_status()
        if api_status["status"] == "healthy" and api_status["model_loaded"]:
            st.success(f"✅ ML Model v{api_status['model_version']}")
        elif api_status["status"] == "healthy":
            st.warning("⚠️ Model chưa train")
        else:
            st.error("❌ FastAPI offline")
        
        # Test buttons row
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("🧪", key="test_gemini", help="Test Gemini API"):
                test_gemini_connection(gemini_key)
        with col2:
            if st.button("ℹ️", key="model_info", help="Model Info"):
                show_model_info()
        with col3:
            if st.button("🔌", key="test_trino", help="Test Trino"):
                test_trino_db()

def test_gemini_connection(api_key: str):
    """Test Gemini API connection"""
    with st.spinner("Testing..."):
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            llm = ChatGoogleGenerativeAI(
                model="gemini-2.5-flash-lite",
                temperature=0,
                google_api_key=api_key,
                convert_system_message_to_human=True
            )
            response = llm.invoke("Hello")
            st.success("✅ Gemini hoạt động tốt!")
            st.caption(f"Response: {response.content[:100]}...")
        except Exception as e:
            st.error(f"❌ Lỗi: {str(e)[:100]}")

def show_model_info():
    """Show model information"""
    from utils.api_client import get_model_info
    with st.spinner("Loading..."):
        info_result = get_model_info()
        if info_result["success"]:
            st.success("⚙️ Model Details")
            st.json(info_result["data"])
        else:
            st.error(f"❌ {info_result['error']}")

def test_trino_db():
    """Test Trino connection"""
    with st.spinner("Testing..."):
        result = test_trino_connection()
        if result["success"]:
            st.success(f"✅ {result['count']:,} records")
        else:
            st.error(f"❌ {result['error'][:50]}")

def render_session_manager(current_session: str, on_new_chat, on_load_session) -> Optional[str]:
    """Quản lý sessions"""
    
    with st.expander("💬 Sessions", expanded=False):
        # New chat button
        if st.button("➕ Chat mới", use_container_width=True):
            return on_new_chat()
    
        # Load existing sessions
        sessions = get_all_sessions()
        if sessions:
            st.caption(f"{len(sessions)} sessions")
            
            for session in sessions[:10]:  # Limit 10
                col1, col2 = st.columns([4, 1])
                
                with col1:
                    session_label = f"{session['session_id'][:8]}... ({session['message_count']})"
                    if st.button(session_label, key=f"load_{session['session_id']}", use_container_width=True):
                        return on_load_session(session['session_id'])
                
                with col2:
                    if st.button("🗑️", key=f"del_{session['session_id']}"):
                        delete_session(session['session_id'])
                        st.rerun()
    
    return None

def render_tools():
    """Các công cụ bổ sung"""
    
    # Manual Prediction Form
    with st.expander("✍️ Manual Prediction", expanded=False):
        form = ManualPredictionForm()
        result = form.render()
        
        if result:
            # Lưu kết quả vào session state để main.py xử lý
            st.session_state.manual_prediction_result = result
            st.rerun()
    
    # CSV Upload
    with st.expander("📤 Batch Upload", expanded=False):
        uploader = CSVBatchUploader()
        uploader.render()
    
    # Clear cache
    if st.button("🗑️ Clear Cache", use_container_width=True):
        st.cache_resource.clear()
        st.success("✅ Cache cleared!")
        st.rerun()

def render_examples():
    """Câu hỏi mẫu"""
    with st.expander("💡 Examples", expanded=False):
        st.markdown("""
**📊 Analytics:**
- Top 5 bang có fraud rate cao nhất
- Merchant nguy hiểm nhất  
- Fraud rate theo giờ trong ngày

**🔮 Prediction:**
- Dự đoán giao dịch $850 lúc 2h sáng
- Check giao dịch $1200 xa 150km
- Thông tin model
        """)
