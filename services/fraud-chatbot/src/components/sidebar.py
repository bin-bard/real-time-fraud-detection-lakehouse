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
    """Test Gemini API connection - Direct API call"""
    with st.spinner("Testing..."):
        try:
            import google.generativeai as genai
            from core.config import GEMINI_MODEL_NAME, GEMINI_TEST_TIMEOUT
            
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(GEMINI_MODEL_NAME)
            
            # Quick test with timeout
            response = model.generate_content(
                "Say 'OK' if you can read this.",
                request_options={"timeout": GEMINI_TEST_TIMEOUT}
            )
            
            st.success("✅ Gemini API hoạt động!")
            st.caption(f"Model: {GEMINI_MODEL_NAME}")
        except Exception as e:
            error_msg = str(e)
            if "429" in error_msg or "quota" in error_msg.lower():
                st.warning("⚠️ Quota exceeded (20 requests/day). API vẫn hoạt động nhưng hết quota.")
            elif "timeout" in error_msg.lower():
                st.error("❌ Timeout - API quá chậm")
            else:
                st.error(f"❌ Lỗi: {error_msg[:150]}")

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
### ⚡ **Phân tích dữ liệu**

**Về Fraud Rate:**
- Bang nào có tỉ lệ gian lận cao nhất?
- Cho tôi xem top 5 bang nguy hiểm nhất
- So sánh fraud rate giữa các bang
- Bang nào an toàn nhất?

**Về Merchants:**
- Merchant nào nguy hiểm nhất?
- Liệt kê 10 merchant có fraud rate >10%
- Phân tích merchant có nhiều giao dịch lạ
- Walmart có an toàn không?
- Merchant grocery nào đáng tin cậy?

**Về Thời gian:**
- Giờ nào hay có gian lận nhất?
- Fraud rate theo giờ trong ngày
- Cuối tuần có nhiều fraud hơn không?
- Đêm khuya (2-4h sáng) nguy hiểm như thế nào?
- Phân tích xu hướng theo giờ

**Về Categories:**
- Category nào bị fraud nhiều nhất?
- Shopping online có rủi ro không?
- Gas station có hay bị gian lận không?

**Về Xu hướng:**
- Xu hướng 7 ngày qua
- Có pattern nào lặp lại không?
- Fraud rate trung bình là bao nhiêu?

---

### 🔮 **Dự đoán giao dịch**

**Simple:**
- Dự đoán giao dịch 850 đô
- Check giao dịch $1200
- Giao dịch $50 có an toàn không?
- Thanh toán $300 có rủi ro không?

**Với context:**
- Giao dịch $850 lúc 2h sáng nguy hiểm không?
- Check giao dịch $1200 xa 150km
- Đi mua hàng $500 lúc 3h sáng
- Mua gas $80 lúc 11h trưa

**Detailed:**
- Khách 45 tuổi, giao dịch $3000 lúc 1h sáng, xa 200km
- Giao dịch gas_transport $150, khách hàng 60 tuổi
- Nữ 30 tuổi, mua shopping_net $1500, xa nhà 50km

**Comparison:**
- So sánh giao dịch 100 đô và 1000 đô
- Nếu tôi mua hàng $500 lúc 2h sáng vs 2h chiều thì sao?

---

### ℹ️ **Thông tin hệ thống**

- Model hiện tại là gì?
- Cho tôi xem thông tin model
- Độ chính xác của model bao nhiêu?
- Model được train khi nào?
- Có bao nhiêu features được dùng?
- AUC score là gì?

---

### ✨ **Câu hỏi phức hợp**

- Giao dịch $1500 lúc 3h sáng có rủi ro không? So sánh với fraud rate trung bình.
- Top 3 bang có fraud rate cao và dự đoán giao dịch $800 từ bang đó
- Liệt kê merchant grocery có fraud >5% và check giao dịch $200 tại đó
- Phân tích xu hướng fraud tuần này và dự đoán $1000 lúc 2h sáng
        """)
