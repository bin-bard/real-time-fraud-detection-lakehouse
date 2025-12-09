"""
Chat Bubble Component
Render tin nhắn chat với formatting đẹp
"""

import streamlit as st
from typing import Dict, Optional

def render_message(msg: Dict, show_sql: bool = True):
    """Render một tin nhắn chat với formatting đẹp"""
    
    role = msg.get("role", "user")
    content = msg.get("content", "")
    sql_query = msg.get("sql_query")
    
    with st.chat_message(role):
        # Message content
        st.markdown(content)
        
        # SQL query (nếu có)
        if show_sql and sql_query:
            with st.expander("🔍 SQL Query"):
                st.code(sql_query, language="sql")
        
        # Prediction details (nếu có)
        if "prediction_data" in msg:
            render_prediction_details(msg["prediction_data"])

def render_prediction_details(data: Dict):
    """Hiển thị chi tiết prediction"""
    
    risk_level = data.get("risk_level", "UNKNOWN")
    probability = data.get("fraud_probability", 0)
    
    # Risk emoji
    risk_emoji = {
        "LOW": "🟢",
        "MEDIUM": "🟡",
        "HIGH": "🔴"
    }.get(risk_level, "⚪")
    
    # Display metrics (NO nested expander)
    st.markdown(f"### {risk_emoji} Chi tiết dự đoán")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Risk Level", risk_level)
    with col2:
        st.metric("Probability", f"{probability:.1%}")
    with col3:
        st.metric("Model", data.get("model_version", "N/A"))
    
    # Explanation
    if "explanation" in data:
        st.markdown("**💬 Giải thích:**")
        st.info(data["explanation"])
    
    # Model info (as JSON, not expander)
    if "model_info" in data:
        st.markdown("**⚙️ Model Details:**")
        st.json(data["model_info"])

def render_thinking_process(steps):
    """Hiển thị quá trình suy nghĩ của Agent"""
    
    if not steps:
        return
    
    with st.expander("🧠 Agent Thinking Process"):
        for i, step in enumerate(steps, 1):
            if isinstance(step, tuple) and len(step) >= 2:
                action, observation = step
                
                st.markdown(f"**Bước {i}:**")
                
                # Action
                if hasattr(action, 'tool'):
                    st.code(f"Tool: {action.tool}\nInput: {action.tool_input}", language="text")
                
                # Observation (limit length)
                obs_str = str(observation)
                if len(obs_str) > 500:
                    obs_str = obs_str[:500] + "..."
                st.text_area(f"Output {i}", obs_str, height=100, key=f"obs_{i}")
                
                st.markdown("---")
