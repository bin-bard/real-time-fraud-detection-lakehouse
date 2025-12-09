"""
Trino Delta Lake Connection
Thực thi SQL queries và trả về kết quả
"""

from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool
from typing import Dict, List
import os

def get_trino_engine():
    """Tạo Trino engine"""
    trino_host = os.getenv("TRINO_HOST", "trino")
    trino_port = os.getenv("TRINO_PORT", "8081")
    trino_user = os.getenv("TRINO_USER", "admin")
    trino_catalog = os.getenv("TRINO_CATALOG", "delta")
    trino_schema = os.getenv("TRINO_SCHEMA", "gold")
    
    trino_uri = f"trino://{trino_user}@{trino_host}:{trino_port}/{trino_catalog}/{trino_schema}"
    
    return create_engine(
        trino_uri,
        connect_args={"http_scheme": "http"},
        poolclass=NullPool,
        echo=False
    )

def execute_sql_query(sql: str) -> Dict:
    """
    Thực thi SQL query và trả về kết quả + query string
    FIX: Trả về cả SQL query để lưu vào chat history
    """
    try:
        engine = get_trino_engine()
        
        with engine.connect() as conn:
            result = conn.execute(text(sql))
            
            # Fetch all rows
            rows = result.fetchall()
            columns = result.keys()
            
            # Convert to list of dicts
            data = [
                {col: val for col, val in zip(columns, row)}
                for row in rows
            ]
            
            return {
                "success": True,
                "data": data,
                "sql_query": sql,  # ← FIX: Trả về cả SQL query
                "row_count": len(data)
            }
    
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "sql_query": sql  # ← Cả khi lỗi cũng trả về SQL
        }

def test_trino_connection() -> Dict:
    """Test kết nối Trino"""
    sql = "SELECT COUNT(*) as total FROM fact_transactions"
    result = execute_sql_query(sql)
    
    if result["success"]:
        count = result["data"][0]["total"]
        return {"success": True, "count": count}
    else:
        return {"success": False, "error": result["error"]}

def get_table_list() -> List[str]:
    """Lấy danh sách tables trong schema"""
    sql = "SHOW TABLES"
    result = execute_sql_query(sql)
    
    if result["success"]:
        return [row["Table"] for row in result["data"]]
    else:
        return []

def get_table_schema(table_name: str) -> Dict:
    """Lấy schema của table"""
    sql = f"DESCRIBE {table_name}"
    result = execute_sql_query(sql)
    
    if result["success"]:
        return {
            "success": True,
            "columns": [
                {"name": row["Column"], "type": row["Type"]}
                for row in result["data"]
            ]
        }
    else:
        return {"success": False, "error": result["error"]}
