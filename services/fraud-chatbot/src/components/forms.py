"""
Forms Component
- Manual Prediction Form: Nhập thủ công thông tin giao dịch
- CSV Batch Uploader: Upload file CSV để batch prediction
"""

import streamlit as st
import pandas as pd
from typing import Dict, Optional

# Import từ modules khác
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from utils.api_client import predict_batch_api, predict_fraud_raw
from components.prediction_result import get_batch_ai_insight

class ManualPredictionForm:
    """Form nhập thủ công thông tin giao dịch"""
    
    def render(self) -> Optional[Dict]:
        """Render form và trả về kết quả prediction nếu submit"""
        
        with st.form("manual_prediction_form"):
            st.write("**Thông tin giao dịch:**")
            
            # Basic fields
            col1, col2 = st.columns(2)
            with col1:
                amt = st.number_input("💰 Số tiền ($)", min_value=0.0, value=100.0, step=10.0)
                hour = st.number_input("🕐 Giờ (0-23)", min_value=0, max_value=23, value=14)
                distance_km = st.number_input("📍 Khoảng cách (km)", min_value=0.0, value=10.0, step=5.0)
            
            with col2:
                age = st.number_input("👤 Tuổi khách hàng", min_value=18, max_value=100, value=35)
                day_of_week = st.selectbox("📅 Ngày trong tuần", 
                    options=[0,1,2,3,4,5,6],
                    format_func=lambda x: ["Thứ 2","Thứ 3","Thứ 4","Thứ 5","Thứ 6","Thứ 7","CN"][x]
                )
            
            # Optional fields
            merchant = st.text_input("🏪 Merchant (tùy chọn)")
            category = st.selectbox("🏷️ Category (tùy chọn)", 
                ["", "shopping_net", "grocery_pos", "gas_transport", "misc_net", "entertainment", "food_dining"])
            
            # Submit button
            submitted = st.form_submit_button("🔮 Dự đoán", use_container_width=True)
            
            if submitted:
                # Call API with RAW data (không cần tính features)
                result = predict_fraud_raw(
                    amt=amt,
                    hour=hour,
                    distance_km=distance_km,
                    age=age,
                    merchant=merchant if merchant else None,
                    category=category if category else None
                )
                
                if result["success"]:
                    return result["data"]
                else:
                    st.error(f"❌ Lỗi: {result['error']}")
        
        return None


class CSVBatchUploader:
    """Upload CSV để batch prediction"""
    
    def render(self):
        """Render uploader và xử lý batch"""
        
        st.write("**Upload CSV với các cột:**")
        st.code("amt,hour,distance_km,age,merchant,category")
        
        # Download template
        template_df = pd.DataFrame({
            "amt": [100.0, 850.0, 1200.0],
            "hour": [14, 2, 23],
            "distance_km": [10.0, 150.0, 5.0],
            "age": [35, 45, 28],
            "merchant": ["Shop A", "Shop B", "Shop C"],
            "category": ["shopping_net", "gas_transport", "misc_net"]
        })
        
        csv_template = template_df.to_csv(index=False)
        st.download_button(
            label="📥 Download Template CSV",
            data=csv_template,
            file_name="batch_template.csv",
            mime="text/csv",
            use_container_width=True
        )
        
        st.markdown("---")
        
        uploaded_file = st.file_uploader("Chọn file CSV", type=["csv"])
        
        if uploaded_file:
            try:
                df = pd.read_csv(uploaded_file)
                st.write(f"✅ Đọc được {len(df)} giao dịch")
                
                # Preview - NO expander (already in Batch Upload expander)
                st.caption("👀 Preview:")
                st.dataframe(df.head(), use_container_width=True)
                
                # Predict button
                if st.button("🔮 Batch Predict", use_container_width=True):
                    self._process_batch(df)
                    
            except Exception as e:
                st.error(f"❌ Lỗi đọc file: {str(e)}")
    
    def _process_batch(self, df: pd.DataFrame):
        """Xử lý batch prediction với raw data"""
        
        # Convert to list of raw transactions (không cần build features)
        transactions = []
        for _, row in df.iterrows():
            trans = {
                "amt": float(row.get('amt', 0))
            }
            
            # Add optional fields if present
            if 'hour' in row and pd.notna(row['hour']):
                trans["hour"] = int(row['hour'])
            if 'distance_km' in row and pd.notna(row['distance_km']):
                trans["distance_km"] = float(row['distance_km'])
            if 'age' in row and pd.notna(row['age']):
                trans["age"] = int(row['age'])
            if 'merchant' in row and pd.notna(row['merchant']):
                trans["merchant"] = str(row['merchant'])
            if 'category' in row and pd.notna(row['category']):
                trans["category"] = str(row['category'])
            
            transactions.append(trans)
        
        # Call batch API
        with st.spinner(f"🔮 Đang xử lý {len(transactions)} giao dịch..."):
            result = predict_batch_api(transactions)
        
        if result["success"]:
            data = result["data"]
            summary = data.get("summary", {})
            
            # Generate AI insight using shared component
            with st.spinner("🤖 Đang phân tích kết quả batch..."):
                batch_insight = get_batch_ai_insight(summary)
            
            # Display AI insight first
            st.info(batch_insight)
            
            # Display summary
            st.success(f"""
### 📊 Kết quả Batch Prediction

- **Tổng giao dịch:** {summary.get('total_transactions', 0)}
- **Phát hiện gian lận:** {summary.get('fraud_detected', 0)} ({summary.get('fraud_rate', 0):.1f}%)
- **High risk:** {summary.get('high_risk_count', 0)}
- **Model:** {summary.get('model_version', 'N/A')}
            """)
            
            # Results table
            predictions = data.get("predictions", [])
            if predictions:
                results_df = pd.DataFrame(predictions)
                st.dataframe(results_df, use_container_width=True)
                
                # Download button
                csv = results_df.to_csv(index=False)
                st.download_button(
                    label="📥 Tải kết quả CSV",
                    data=csv,
                    file_name=f"batch_predictions_{pd.Timestamp.now():%Y%m%d_%H%M%S}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
        else:
            st.error(f"❌ Lỗi: {result['error']}")
