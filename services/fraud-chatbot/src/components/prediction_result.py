"""
Prediction Result Component
Format và display kết quả prediction từ API với AI insights
DÙNG CHUNG cho: Manual, Batch, Chatbot
"""

import streamlit as st
from typing import Dict, Optional
from langchain_google_genai import ChatGoogleGenerativeAI
import os

def get_ai_insight(prediction_result: Dict) -> str:
    """
    Gọi Gemini API để tạo insights từ kết quả prediction
    
    Args:
        prediction_result: Kết quả từ /predict hoặc /predict/raw endpoint
        
    Returns:
        str: AI-generated insights (plain text, no markdown)
    """
    
    # Extract key info
    fraud_prob = prediction_result.get("fraud_probability", 0)
    is_fraud = prediction_result.get("is_fraud_predicted", 0)
    risk_level = prediction_result.get("risk_level", "UNKNOWN")
    feature_explanation = prediction_result.get("feature_explanation", "")
    amt = prediction_result.get("raw_input", {}).get("amt", 0)
    
    # Build prompt
    prompt = f"""
Bạn là chuyên gia phân tích gian lận tài chính. Hãy giải thích kết quả dự đoán sau một cách ngắn gọn (2-3 câu):

**Kết quả từ API:**
- Giao dịch: ${amt:.2f}
- Xác suất gian lận: {fraud_prob:.1%}
- Kết luận: {"GIAN LẬN" if is_fraud else "HỢP LỆ"}
- Mức độ rủi ro: {risk_level}

**Phân tích kỹ thuật từ model:**
{feature_explanation if feature_explanation else "Không có thông tin chi tiết"}

Viết phân tích ngắn gọn bằng TIẾNG VIỆT với:
1. Đánh giá chung (an toàn/cảnh báo/nguy hiểm) 
2. Lý do chính dựa trên features
3. Khuyến nghị hành động cụ thể

KHÔNG dùng emoji, KHÔNG format markdown (chỉ text thuần).
"""

    try:
        # Call Gemini API
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash-exp",
            google_api_key=os.getenv("GOOGLE_API_KEY"),
            temperature=0.3,
            max_tokens=200
        )
        
        response = llm.invoke(prompt)
        return response.content.strip()
        
    except Exception as e:
        # Fallback nếu Gemini fail
        if is_fraud:
            return f"Giao dịch ${amt:.2f} có xác suất gian lận {fraud_prob:.1%} (mức {risk_level}). Khuyến nghị từ chối hoặc xác minh bổ sung."
        else:
            return f"Giao dịch ${amt:.2f} an toàn với xác suất gian lận thấp {fraud_prob:.1%}. Có thể phê duyệt nhưng vẫn cần theo dõi."


def get_batch_ai_insight(summary: Dict) -> str:
    """
    Gọi Gemini API để phân tích batch summary
    
    Args:
        summary: Summary từ batch API
        
    Returns:
        str: AI-generated insights cho batch results
    """
    
    total = summary.get('total_transactions', 0)
    fraud_count = summary.get('fraud_detected', 0)
    fraud_rate = summary.get('fraud_rate', 0)
    high_risk = summary.get('high_risk_count', 0)
    
    prompt = f"""
Bạn là chuyên gia phân tích gian lận tài chính. Hãy đánh giá kết quả batch prediction sau:

**Kết quả từ API:**
- Tổng giao dịch: {total}
- Gian lận phát hiện: {fraud_count} ({fraud_rate:.1f}%)
- High risk: {high_risk}

Viết đánh giá ngắn gọn (2-3 câu) bằng TIẾNG VIỆT với:
1. Đánh giá tỉ lệ gian lận (cao/bình thường/thấp)
2. Mức độ rủi ro của batch
3. Khuyến nghị hành động

KHÔNG dùng emoji, KHÔNG format markdown (chỉ text thuần).
"""

    try:
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash-exp",
            google_api_key=os.getenv("GOOGLE_API_KEY"),
            temperature=0.3,
            max_tokens=200
        )
        
        response = llm.invoke(prompt)
        return response.content.strip()
        
    except Exception as e:
        # Fallback
        if fraud_rate > 10:
            return f"CẢNH BÁO: Tỉ lệ gian lận rất cao ({fraud_rate:.1f}%). Cần kiểm tra kỹ nguồn dữ liệu và các giao dịch HIGH RISK."
        elif fraud_rate > 5:
            return f"CHÚ Ý: Tỉ lệ gian lận cao hơn bình thường ({fraud_rate:.1f}%). Xem xét các giao dịch được đánh dấu để tìm pattern."
        else:
            return f"Tỉ lệ gian lận trong mức kiểm soát ({fraud_rate:.1f}%). Tiếp tục giám sát thường xuyên."


def format_prediction_message(result: Dict, ai_insight: str) -> str:
    """
    Format prediction result thành markdown message
    DÙNG CHUNG cho Manual và Chatbot để đồng nhất format
    
    Args:
        result: Kết quả từ API
        ai_insight: AI-generated insight text
        
    Returns:
        str: Formatted markdown message
    """
    
    fraud_icon = "⚠️" if result.get('is_fraud_predicted') == 1 else "✅"
    risk_emoji_map = {"LOW": "🟢", "MEDIUM": "🟡", "HIGH": "🔴"}
    risk_emoji = risk_emoji_map.get(result.get('risk_level', ''), "⚪")
    
    return f"""
{fraud_icon} **Kết quả Dự đoán**

{ai_insight}

---

**Chi tiết kỹ thuật:**
- **Xác suất gian lận:** {result.get('fraud_probability', 0):.1%}
- **Risk Level:** {risk_emoji} {result.get('risk_level', 'UNKNOWN')}  
- **Model:** {result.get('model_version', 'N/A')}
- **Transaction ID:** `{result.get('trans_num', 'N/A')}`
""".strip()


def display_prediction_result(result: Dict, source: str = "Manual"):
    """
    Display prediction result với AI insight
    DÙNG CHUNG cho tất cả sources
    
    Args:
        result: Kết quả từ API
        source: "Manual", "Chatbot", hoặc "Batch"
    """
    
    with st.spinner("🤖 Đang phân tích kết quả..."):
        ai_insight = get_ai_insight(result)
    
    formatted_msg = format_prediction_message(result, ai_insight)
    
    # Display formatted message
    st.markdown(formatted_msg)
    
    # Additional details if needed
    if "feature_explanation" in result and result["feature_explanation"]:
        with st.expander("📊 Chi tiết features"):
            st.text(result["feature_explanation"])
