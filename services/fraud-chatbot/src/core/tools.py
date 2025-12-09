"""
LangChain Tools cho Fraud Detection Agent
- QueryDatabaseTool: Query Trino Delta Lake
- PredictFraudTool: Dự đoán fraud bằng ML model
"""

from langchain.tools import Tool
from langchain.pydantic_v1 import BaseModel, Field
from typing import Optional
import pandas as pd
import math

# Import từ modules khác
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from database.trino import execute_sql_query
from utils.api_client import predict_fraud_api

class QueryDatabaseInput(BaseModel):
    """Input cho QueryDatabaseTool"""
    sql_query: str = Field(description="SQL query cần thực thi trên Trino")

class PredictFraudInput(BaseModel):
    """Input cho PredictFraudTool"""
    amt: float = Field(description="Số tiền giao dịch (USD)")
    hour: Optional[int] = Field(None, description="Giờ giao dịch (0-23)")
    distance_km: Optional[float] = Field(None, description="Khoảng cách từ địa chỉ khách hàng (km)")
    merchant: Optional[str] = Field(None, description="Tên merchant")
    category: Optional[str] = Field(None, description="Loại giao dịch")
    age: Optional[int] = Field(None, description="Tuổi khách hàng")

def create_database_tool():
    """Công cụ truy vấn database"""
    
    def query_database(sql_query: str) -> str:
        """Thực thi SQL query và trả về kết quả"""
        result = execute_sql_query(sql_query)
        
        if result["success"]:
            data = result["data"]
            if data:
                # Format as markdown table
                df = pd.DataFrame(data)
                
                # Limit to 20 rows để tránh quá dài
                if len(df) > 20:
                    df = df.head(20)
                    return f"Kết quả query (hiển thị 20/{result['row_count']} rows):\n\n{df.to_markdown(index=False)}"
                else:
                    return f"Kết quả query:\n\n{df.to_markdown(index=False)}"
            else:
                return "Query thành công nhưng không có dữ liệu."
        else:
            return f"Lỗi query: {result['error']}"
    
    return Tool(
        name="QueryDatabase",
        func=query_database,
        description="""
Công cụ truy vấn Trino Delta Lake (catalog: delta, schema: gold).

Sử dụng khi cần:
- Phân tích dữ liệu thống kê (fraud rate, top merchants, trends...)
- Đếm số lượng, tính tổng, trung bình
- Lấy thông tin lịch sử từ fact_transactions, dim_customer, dim_merchant

Bảng quan trọng (ƯU TIÊN dùng bảng pre-aggregated để NHANH):
- state_summary: Fraud rate theo bang (pre-aggregated - NHANH)
- merchant_analysis: Top merchants rủi ro (pre-aggregated - NHANH)
- hourly_summary, daily_summary: Trends theo thời gian (pre-aggregated)
- fact_transactions: Giao dịch chi tiết (chậm hơn, chỉ dùng khi cần)
- dim_customer, dim_merchant: Thông tin chiều

Input: SQL query string (phải hợp lệ Trino SQL)
Output: Kết quả dạng bảng markdown

Ví dụ queries:
- SELECT state, fraud_rate FROM state_summary ORDER BY fraud_rate DESC LIMIT 5
- SELECT merchant, fraud_count FROM merchant_analysis WHERE fraud_count > 100
- SELECT hour, avg_amount FROM hourly_summary WHERE hour BETWEEN 0 AND 6
        """
    )

def create_prediction_tool():
    """Công cụ dự đoán gian lận"""
    
    def predict_fraud(amt: float, hour: int = None, distance_km: float = None, 
                     merchant: str = None, category: str = None, age: int = None) -> str:
        """Dự đoán giao dịch có gian lận không"""
        
        # Build features (simplified version)
        features = {
            "amt": amt,
            "log_amount": math.log1p(amt),
            "is_high_amount": 1 if amt > 500 else 0,
            "is_zero_amount": 1 if amt == 0 else 0,
            "amount_bin": min(5, max(1, int(amt / 100) + 1)) if amt > 0 else 0,
            "distance_km": distance_km or 10.0,
            "is_distant_transaction": 1 if (distance_km or 0) > 50 else 0,
            "age": age or 35,
            "gender_encoded": 0,
            "hour": hour or 12,
            "day_of_week": 0,
            "is_weekend": 0,
            "is_late_night": 1 if hour and (hour < 6 or hour >= 23) else 0,
            "hour_sin": math.sin(2 * math.pi * (hour or 12) / 24),
            "hour_cos": math.cos(2 * math.pi * (hour or 12) / 24),
            "merchant": merchant,
            "category": category,
            "trans_num": f"CHAT_{pd.Timestamp.now():%Y%m%d%H%M%S}"
        }
        
        # Call API
        result = predict_fraud_api(features)
        
        if result["success"]:
            data = result["data"]
            fraud_icon = "⚠️" if data['is_fraud_predicted'] == 1 else "✅"
            risk_emoji_map = {"LOW": "🟢", "MEDIUM": "🟡", "HIGH": "🔴"}
            risk_emoji = risk_emoji_map.get(data['risk_level'], "⚪")
            
            return f"""
{fraud_icon} Kết quả dự đoán:
- Fraud: {'CÓ' if data['is_fraud_predicted'] == 1 else 'KHÔNG'}
- Probability: {data['fraud_probability']:.1%}
- Risk Level: {risk_emoji} {data['risk_level']}

{data.get('explanation', '')}
            """
        else:
            return f"❌ Lỗi prediction: {result['error']}"
    
    return Tool(
        name="PredictFraud",
        func=predict_fraud,
        description="""
Công cụ dự đoán giao dịch có gian lận hay không bằng ML model.

Sử dụng khi cần:
- Kiểm tra giao dịch mới có rủi ro không
- Đánh giá scenario giả định
- So sánh các giao dịch khác nhau

Input bắt buộc:
- amt: Số tiền giao dịch (float, ví dụ: 500.0)

Input tùy chọn (càng nhiều càng chính xác):
- hour: Giờ giao dịch (0-23)
- distance_km: Khoảng cách từ nhà khách hàng
- merchant: Tên merchant
- category: Loại giao dịch
- age: Tuổi khách hàng

Output: Kết quả dự đoán với giải thích chi tiết

Ví dụ:
- PredictFraud(amt=850.0, hour=2, distance_km=150.0)
- PredictFraud(amt=1200.0)
        """
    )
