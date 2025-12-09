"""
LangChain Tools cho Fraud Detection Agent
- QueryDatabaseTool: Query Trino Delta Lake
- PredictFraudTool: Dự đoán fraud bằng ML model
"""

from langchain.tools import Tool, StructuredTool
from langchain.pydantic_v1 import BaseModel, Field
from typing import Optional, Union, Dict, Any
import pandas as pd
import math
import json

# Import từ modules khác
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from database.trino import execute_sql_query
from utils.api_client import predict_fraud_api

class QueryDatabaseInput(BaseModel):
    """Input cho QueryDatabaseTool"""
    sql_query: str = Field(description="SQL query cần thực thi trên Trino")

# Không dùng Pydantic schema cho PredictFraud vì LangChain sẽ validate sai
# Thay vào đó dùng infer_schema=True trong StructuredTool

def create_database_tool():
    """Công cụ truy vấn database"""
    
    def query_database(sql_query: str) -> str:
        """Thực thi SQL query và trả về kết quả"""
        # Parse JSON nếu agent truyền vào dạng {"query": "..."}
        import json
        if sql_query.strip().startswith('{'):
            try:
                parsed = json.loads(sql_query)
                sql_query = parsed.get('query', sql_query)
            except:
                pass  # Nếu không parse được thì giữ nguyên
        
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
- Xem thông tin model: fraud_predictions table có model_version, fraud_probability

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

def get_ai_insight(prediction_result: dict, llm=None) -> str:
    """Generate AI insight using Gemini if available"""
    if not llm:
        return ""  # No LLM, skip insights
    
    try:
        is_fraud = prediction_result.get('is_fraud')
        probability = prediction_result.get('probability', 0)
        amt = prediction_result.get('amt', 0)
        hour = prediction_result.get('hour', 12)
        distance = prediction_result.get('distance', 0)
        
        prompt = f"""
Phân tích giao dịch tài chính:
- Kết quả model: {'GIAN LẬN' if is_fraud else 'AN TOÀN'}
- Xác suất gian lận: {probability:.1%}
- Số tiền: ${amt}
- Thời gian: {hour}h
- Khoảng cách: {distance}km

Viết 2-3 dòng insight ngắn gọn (tiếng Việt) về giao dịch này.
"""
        
        from langchain.schema import HumanMessage
        response = llm.invoke([HumanMessage(content=prompt)])
        return f"\n\n💡 **AI Insight:**\n{response.content.strip()}"
        
    except Exception as e:
        return ""  # Fail silently

def create_prediction_tool(llm=None):
    """Công cụ dự đoán gian lận với AI insights"""
    
    def predict_fraud(
        amt: Union[float, str] = None,
        hour: Optional[int] = None,
        distance_km: Optional[float] = None,
        merchant: Optional[str] = None,
        category: Optional[str] = None,
        age: Optional[int] = None
    ) -> str:
        """
        Dự đoán giao dịch có gian lận không
        
        Args:
            amt: Số tiền giao dịch (bắt buộc)
            hour: Giờ giao dịch (0-23)
            distance_km: Khoảng cách từ nhà (km)
            merchant: Tên merchant
            category: Loại giao dịch
            age: Tuổi khách hàng
        """
        
        # WORKAROUND: LangChain đôi khi truyền toàn bộ JSON dict vào amt parameter
        if isinstance(amt, str) and amt.strip().startswith('{'):
            try:
                input_dict = json.loads(amt)
                amt = input_dict.get('amt')
                hour = input_dict.get('hour', hour)
                distance_km = input_dict.get('distance_km', distance_km)
                merchant = input_dict.get('merchant', merchant)
                category = input_dict.get('category', category)
                age = input_dict.get('age', age)
            except json.JSONDecodeError:
                pass  # Keep original amt value
        
        # Parse amount
        try:
            if amt is None:
                return "❌ Lỗi: Thiếu tham số 'amt' (số tiền giao dịch)"
            amt = float(amt)
        except (ValueError, TypeError) as e:
            return f"❌ Lỗi parse số tiền: {str(e)}"
        
        # Validate amt
        if amt <= 0:
            return "❌ Lỗi: Số tiền giao dịch phải > 0"
        
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
            is_fraud = data.get('is_fraud_predicted', 0)
            probability = data.get('fraud_probability', 0)
            risk = data.get('risk_level', 'UNKNOWN')
            model_ver = data.get('model_version', 'N/A')
            
            # Risk emoji
            risk_emoji = {"LOW": "🟢", "MEDIUM": "🟡", "HIGH": "🔴"}.get(risk, "⚪")
            
            # AI insights (only if using ML model and LLM available)
            ai_insight = ""
            if llm and "mlflow" in model_ver.lower():
                ai_insight = get_ai_insight({
                    'is_fraud': is_fraud,
                    'probability': probability,
                    'amt': amt,
                    'hour': hour or 12,
                    'distance': distance_km or 10
                }, llm)
            
            return f"""
✅ **Kết quả dự đoán**

Giao dịch ${amt:.2f}:
- **Fraud:** {'CÓ' if is_fraud == 1 else 'KHÔNG'}
- **Xác suất:** {probability:.1%}
- **Risk Level:** {risk_emoji} {risk}
- **Model:** {model_ver}{ai_insight}
"""
        else:
            return f"❌ Lỗi prediction: {result['error']}"
    
    # Dùng StructuredTool với infer_schema thay vì args_schema
    return StructuredTool.from_function(
        func=predict_fraud,
        name="PredictFraud",
        description="""
Công cụ dự đoán giao dịch có gian lận hay không bằng ML model.

Sử dụng khi cần:
- Kiểm tra giao dịch mới có rủi ro không
- Đánh giá scenario giả định
- So sánh các giao dịch khác nhau

Input:
- amt: Số tiền giao dịch (BẮT BUỘC, kiểu float hoặc int)
- hour: Giờ giao dịch 0-23 (tùy chọn, kiểu int)
- distance_km: Khoảng cách từ nhà (tùy chọn, kiểu float)
- merchant: Tên merchant (tùy chọn, kiểu string)
- category: Loại giao dịch (tùy chọn, kiểu string)
- age: Tuổi khách hàng (tùy chọn, kiểu int)

Output: Kết quả dự đoán với giải thích

Ví dụ:
- PredictFraud(amt=850.0, hour=2)
- PredictFraud(amt=1200.0, distance_km=150.0)
- PredictFraud(amt=500)
        """,
        handle_tool_error=True
    )
