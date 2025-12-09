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
        
        # API Status
        render_api_status()
        
        st.markdown("---")
        
        # Session Management
        new_session = render_session_manager(session_id, on_new_chat, on_load_session)
        
        st.markdown("---")
        
        # Tools
        render_tools()
        
        st.markdown("---")
        
        # Examples
        render_examples()
        
        return new_session

def render_api_status():
    """Hiển thị trạng thái API và connections"""
    st.subheader("⚙️ System Status")
    
    # 1. Gemini API Key Check
    gemini_key = os.getenv("GOOGLE_API_KEY", "")
    if gemini_key and len(gemini_key) > 20:
        st.success(f"✅ Gemini API: Connected ({gemini_key[:10]}...)")
        
        # Test Gemini connection
        if st.button("🧪 Test Gemini", use_container_width=True, key="test_gemini"):
            with st.spinner("Đang test Gemini API..."):
                try:
                    from langchain_google_genai import ChatGoogleGenerativeAI
                    llm = ChatGoogleGenerativeAI(
                        model="gemini-2.5-flash-lite",
                        temperature=0,
                        google_api_key=gemini_key,
                        convert_system_message_to_human=True
                    )
                    response = llm.invoke("Hello")
                    st.success("✅ Gemini API hoạt động tốt!")
                    st.info(f"Response: {response.content[:100]}...")
                except Exception as e:
                    st.error(f"❌ Gemini API lỗi: {str(e)}")
    else:
        st.error("❌ Gemini API Key chưa config")
        st.info("💡 Set GOOGLE_API_KEY trong file .env")
    
    st.markdown("---")
    
    # 2. FastAPI ML Model Status
    api_status = get_fraud_api_status()
    if api_status["status"] == "healthy":
        if api_status["model_loaded"]:
            st.success(f"✅ ML Model v{api_status['model_version']}")
            
            # Show model info button
            if st.button("ℹ️ Model Info", use_container_width=True, key="model_info"):
                from utils.api_client import get_model_info
                with st.spinner("Đang lấy thông tin model..."):
                    info_result = get_model_info()
                    if info_result["success"]:
                        st.json(info_result["data"])
                    else:
                        st.error(f"❌ {info_result['error']}")
        else:
            st.warning("⚠️ Model chưa train")
    else:
        st.error(f"❌ FastAPI offline: {api_status.get('message', 'Unknown')}")
    
    st.markdown("---")
    
    # 3. Database connection test
    if st.button("🔌 Test Trino", use_container_width=True, key="test_trino"):
        with st.spinner("Đang test Trino..."):
            result = test_trino_connection()
            if result["success"]:
                st.success(f"✅ Trino: {result['count']:,} records")
            else:
                st.error(f"❌ Trino: {result['error']}")

def render_session_manager(current_session: str, on_new_chat, on_load_session) -> Optional[str]:
    """Quản lý sessions"""
    st.subheader("💬 Sessions")
    
    # New chat button
    if st.button("➕ Chat mới", use_container_width=True):
        return on_new_chat()
    
    # Load existing sessions
    sessions = get_all_sessions()
    if sessions:
        st.write(f"**{len(sessions)} sessions:**")
        
        for session in sessions[:10]:  # Limit 10
            col1, col2 = st.columns([4, 1])
            
            with col1:
                session_label = f"{session['session_id'][:8]}... ({session['message_count']} msgs)"
                if st.button(session_label, key=f"load_{session['session_id']}", use_container_width=True):
                    return on_load_session(session['session_id'])
            
            with col2:
                if st.button("🗑️", key=f"del_{session['session_id']}"):
                    delete_session(session['session_id'])
                    st.rerun()
    
    return None

def render_tools():
    """Các công cụ bổ sung"""
    st.subheader("🛠️ Tools")
    
    # Manual Prediction Form
    with st.expander("✍️ Manual Prediction"):
        form = ManualPredictionForm()
        result = form.render()
        
        if result:
            # Lưu kết quả vào session state để main.py xử lý
            st.session_state.manual_prediction_result = result
            st.rerun()
    
    # CSV Upload
    with st.expander("📤 Batch Upload"):
        uploader = CSVBatchUploader()
        uploader.render()
    
    # Clear cache
    if st.button("🗑️ Clear Cache", use_container_width=True):
        st.cache_resource.clear()
        st.success("✅ Cache cleared!")
        st.rerun()

def render_examples():
    """Câu hỏi mẫu"""
    with st.expander("💡 Examples"):
        st.markdown("""
**📊 SQL Analytics:**
- Top 5 bang có fraud rate cao nhất
- Merchant nguy hiểm nhất
- Fraud rate theo giờ trong ngày
- Tổng số giao dịch theo danh mục

**🔮 Prediction:**
- Dự đoán giao dịch $850 lúc 2h sáng
- Check giao dịch $1200 xa 150km
- Kiểm tra $50 mua gas lúc 14h
- Thông tin model

**💼 Phức hợp:**
- Check $500 và so sánh với fraud rate TX
- Dự đoán $1000 và xem top merchant rủi ro

**💬 General:**
- Gian lận tài chính là gì?
- Các pattern fraud phổ biến?
- Làm sao phát hiện fraud?
        """)
