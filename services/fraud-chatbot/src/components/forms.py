"""
Forms Component
- Manual Prediction Form: Nhập thủ công thông tin giao dịch
- CSV Batch Uploader: Upload file CSV để batch prediction
"""

import streamlit as st
import pandas as pd
from typing import Dict, Optional
import math

# Import từ modules khác
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from utils.api_client import predict_fraud_api, predict_batch_api

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
                # Build features
                features = self._build_features(
                    amt=amt,
                    hour=hour,
                    distance_km=distance_km,
                    age=age,
                    day_of_week=day_of_week,
                    merchant=merchant if merchant else None,
                    category=category if category else None
                )
                
                # Call API
                result = predict_fraud_api(features)
                
                if result["success"]:
                    return result["data"]
                else:
                    st.error(f"❌ Lỗi: {result['error']}")
        
        return None
    
    def _build_features(self, amt, hour, distance_km, age, day_of_week, merchant, category):
        """Build complete transaction features"""
        
        # Calculate derived features
        log_amount = math.log1p(amt)
        is_high_amount = 1 if amt > 500 else 0
        is_zero_amount = 1 if amt == 0 else 0
        
        # Amount bin (simplified)
        if amt == 0:
            amount_bin = 0
        elif amt <= 50:
            amount_bin = 1
        elif amt <= 150:
            amount_bin = 2
        elif amt <= 300:
            amount_bin = 3
        elif amt <= 500:
            amount_bin = 4
        else:
            amount_bin = 5
        
        # Distance features
        is_distant = 1 if distance_km > 50 else 0
        
        # Time features
        is_weekend = 1 if day_of_week in [5, 6] else 0
        is_late_night = 1 if hour < 6 or hour >= 23 else 0
        hour_sin = math.sin(2 * math.pi * hour / 24)
        hour_cos = math.cos(2 * math.pi * hour / 24)
        
        # Gender (default F=0)
        gender_encoded = 0
        
        return {
            "amt": amt,
            "log_amount": log_amount,
            "is_zero_amount": is_zero_amount,
            "is_high_amount": is_high_amount,
            "amount_bin": amount_bin,
            "distance_km": distance_km,
            "is_distant_transaction": is_distant,
            "age": age,
            "gender_encoded": gender_encoded,
            "hour": hour,
            "day_of_week": day_of_week,
            "is_weekend": is_weekend,
            "is_late_night": is_late_night,
            "hour_sin": hour_sin,
            "hour_cos": hour_cos,
            "merchant": merchant,
            "category": category,
            "trans_num": f"MANUAL_{pd.Timestamp.now().strftime('%Y%m%d%H%M%S')}"
        }


class CSVBatchUploader:
    """Upload CSV để batch prediction"""
    
    def render(self):
        """Render uploader và xử lý batch"""
        
        st.write("**Upload CSV với các cột:**")
        st.code("amt,hour,distance_km,age,day_of_week,merchant,category")
        
        # Download template
        template_df = pd.DataFrame({
            "amt": [100.0, 850.0, 1200.0],
            "hour": [14, 2, 23],
            "distance_km": [10.0, 150.0, 5.0],
            "age": [35, 45, 28],
            "day_of_week": [0, 5, 6],
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
        """Xử lý batch prediction"""
        
        # Convert to list of features
        transactions = []
        for _, row in df.iterrows():
            form = ManualPredictionForm()
            features = form._build_features(
                amt=row.get('amt', 0),
                hour=int(row.get('hour', 12)),
                distance_km=row.get('distance_km', 10),
                age=int(row.get('age', 35)),
                day_of_week=int(row.get('day_of_week', 0)),
                merchant=row.get('merchant'),
                category=row.get('category')
            )
            transactions.append(features)
        
        # Call batch API
        with st.spinner(f"🔮 Đang xử lý {len(transactions)} giao dịch..."):
            result = predict_batch_api(transactions)
        
        if result["success"]:
            data = result["data"]
            summary = data.get("summary", {})
            
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
