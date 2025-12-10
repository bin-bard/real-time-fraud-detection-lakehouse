"""
LangChain Tools cho Fraud Detection Agent
- QueryDatabaseTool: Query Trino Delta Lake
- PredictFraudTool: Dự đoán fraud bằng ML model (chỉ gửi raw data)
- GetModelInfoTool: Lấy thông tin ML model
"""

from langchain.tools import Tool, StructuredTool
from langchain.pydantic_v1 import BaseModel, Field
from typing import Optional, Union, Dict, Any
import pandas as pd
import json

# Import từ modules khác
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from database.trino import execute_sql_query
from utils.api_client import predict_fraud_raw, get_model_info  # Changed: use predict_fraud_raw

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

def create_prediction_tool(llm=None):
    """
    Công cụ dự đoán gian lận - REFACTORED
    Chỉ gửi raw data cho API, không tự tính features
    """
    
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
        
        # === GỌI API VỚI RAW DATA - API TỰ TÍNH FEATURES ===
        result = predict_fraud_raw(
            amt=amt,
            hour=hour,
            distance_km=distance_km,
            merchant=merchant,
            category=category,
            age=age
        )
        
        if result["success"]:
            data = result["data"]
            is_fraud = data.get('is_fraud_predicted', 0)
            probability = data.get('fraud_probability', 0)
            risk = data.get('risk_level', 'UNKNOWN')
            model_ver = data.get('model_version', 'N/A')
            feature_explanation = data.get('feature_explanation', '')
            
            # Risk emoji
            risk_emoji = {"LOW": "🟢", "MEDIUM": "🟡", "HIGH": "🔴"}.get(risk, "⚪")
            
            # Build response
            response = f"""
✅ **Kết quả dự đoán**

**Giao dịch ${amt:.2f}:**
- **Phát hiện gian lận:** {'✋ CÓ' if is_fraud == 1 else '👍 KHÔNG'}
- **Xác suất:** {probability:.1%}
- **Mức độ rủi ro:** {risk_emoji} {risk}
- **Model version:** {model_ver}
"""
            
            # Add feature explanation if available
            if feature_explanation:
                response += f"\n**Đặc điểm nhận diện:**\n{feature_explanation}\n"
            
            # Add raw input recap
            recap = f"\n**Chi tiết giao dịch:**\n- Số tiền: ${amt:.2f}"
            if hour is not None:
                recap += f"\n- Thời gian: {hour}h"
            if distance_km is not None:
                recap += f"\n- Khoảng cách: {distance_km:.1f}km"
            if merchant:
                recap += f"\n- Merchant: {merchant}"
            if category:
                recap += f"\n- Category: {category}"
            if age:
                recap += f"\n- Tuổi khách hàng: {age} tuổi"
            
            return response + recap
        else:
            return f"❌ Lỗi prediction: {result['error']}"
    
    # Dùng StructuredTool với infer_schema thay vì args_schema
    return StructuredTool.from_function(
        func=predict_fraud,
        name="PredictFraud",
        description="""
Công cụ dự đoán giao dịch có gian lận hay không bằng ML model.

**QUAN TRỌNG:** Chỉ cần gửi dữ liệu thô (raw data), API tự tính toán features.

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
- PredictFraud(amt=50.0, hour=14, merchant="walmart", age=35)
        """,
        infer_schema=True,
        handle_tool_error=True
    )


def create_model_info_tool():
    """Công cụ lấy thông tin model từ API"""
    
    def get_model_information(query: str = "") -> str:
        """Lấy thông tin chi tiết về ML model đang sử dụng"""
        result = get_model_info()
        
        if result["success"]:
            data = result["data"]
            model_type = data.get("model_type", "unknown")
            
            if model_type == "mlflow_model":
                perf = data.get("performance", {})
                return f"""
📊 **Thông tin ML Model**

**Model:** {data.get('model_name', 'N/A')} v{data.get('model_version', 'N/A')}
**Framework:** {data.get('framework', 'N/A')}
**Features:** {data.get('features_count', 'N/A')} features
**Dataset:** {data.get('trained_on', 'N/A')}
**Status:** {data.get('status', 'N/A')}

**Performance Metrics:**
- **Accuracy:** {perf.get('accuracy', 0):.1%}
- **Precision:** {perf.get('precision', 0):.1%}
- **Recall:** {perf.get('recall', 0):.1%}
- **F1-Score:** {perf.get('f1_score', 0):.1%}
- **AUC:** {perf.get('auc', 0):.1%}

**MLflow URI:** {data.get('mlflow_tracking_uri', 'N/A')}
"""
            else:
                return f"""
⚠️ **Model Fallback Mode**

**Model:** Rule-based v{data.get('model_version', '1.0')}
**Framework:** {data.get('framework', 'custom')}
**Status:** {data.get('status', 'fallback')}
**Note:** {data.get('note', 'MLflow model chưa load')}
"""
        else:
            return f"❌ Lỗi lấy thông tin model: {result['error']}"
    
    return Tool(
        name="GetModelInfo",
        func=get_model_information,
        description="""
Công cụ lấy thông tin chi tiết về ML model đang được sử dụng.

Sử dụng khi cần:
- Câu hỏi về "thông tin model", "model hiện tại", "model nào"
- Kiểm tra performance metrics (accuracy, F1, AUC...)
- Xem version model đang dùng
- Kiểm tra trạng thái model (production/fallback)

Input: Không cần tham số
Output: Thông tin chi tiết về model với metrics

Ví dụ câu hỏi:
- "Thông tin model"
- "Model hiện tại là gì?"
- "Accuracy của model bao nhiêu?"
        """
    )
