"""
PostgreSQL Connection
Lưu trữ và quản lý chat history
"""

from sqlalchemy import create_engine, text
from typing import List, Dict, Optional
import streamlit as st
import os

def get_postgres_engine():
    """Kết nối PostgreSQL"""
    postgres_uri = f"postgresql://{os.getenv('POSTGRES_USER', 'postgres')}:{os.getenv('POSTGRES_PASSWORD', 'postgres')}@{os.getenv('POSTGRES_HOST', 'postgres')}:{os.getenv('POSTGRES_PORT', '5432')}/{os.getenv('POSTGRES_DB', 'frauddb')}"
    return create_engine(postgres_uri)

def init_chat_history_table():
    """Tạo bảng lưu lịch sử chat nếu chưa có"""
    engine = get_postgres_engine()
    
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS chat_history (
        id SERIAL PRIMARY KEY,
        session_id VARCHAR(100) NOT NULL,
        role VARCHAR(20) NOT NULL,
        message TEXT NOT NULL,
        sql_query TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    
    CREATE INDEX IF NOT EXISTS idx_session_id ON chat_history(session_id);
    CREATE INDEX IF NOT EXISTS idx_created_at ON chat_history(created_at);
    """
    
    with engine.connect() as conn:
        conn.execute(text(create_table_sql))
        conn.commit()

def save_message(session_id: str, role: str, message: str, sql_query: Optional[str] = None):
    """
    Lưu message VỚI sql_query
    FIX: Truyền sql_query vào INSERT để không bị NULL
    """
    engine = get_postgres_engine()
    
    insert_sql = text("""
        INSERT INTO chat_history (session_id, role, message, sql_query)
        VALUES (:session_id, :role, :message, :sql_query)
    """)
    
    with engine.connect() as conn:
        conn.execute(insert_sql, {
            "session_id": session_id,
            "role": role,
            "message": message,
            "sql_query": sql_query  # ← FIX: Không để NULL nữa
        })
        conn.commit()

def load_chat_history(session_id: str, limit: int = 50) -> List[Dict]:
    """Load lịch sử chat"""
    engine = get_postgres_engine()
    
    query = text("""
        SELECT role, message, sql_query, created_at
        FROM chat_history
        WHERE session_id = :session_id
        ORDER BY created_at
        LIMIT :limit
    """)
    
    with engine.connect() as conn:
        result = conn.execute(query, {"session_id": session_id, "limit": limit})
        
        return [
            {
                "role": row[0],
                "content": row[1],
                "sql_query": row[2],  # ← Lấy sql_query
                "created_at": row[3]
            }
            for row in result
        ]

def get_all_sessions() -> List[Dict]:
    """Lấy danh sách sessions"""
    engine = get_postgres_engine()
    
    query = text("""
        SELECT 
            session_id,
            COUNT(*) as message_count,
            MAX(created_at) as last_message_time
        FROM chat_history
        GROUP BY session_id
        ORDER BY last_message_time DESC
    """)
    
    with engine.connect() as conn:
        result = conn.execute(query)
        
        return [
            {
                "session_id": row[0],
                "message_count": row[1],
                "last_message_time": row[2]
            }
            for row in result
        ]

def delete_session(session_id: str):
    """Xóa session"""
    engine = get_postgres_engine()
    
    delete_sql = text("DELETE FROM chat_history WHERE session_id = :session_id")
    
    with engine.connect() as conn:
        conn.execute(delete_sql, {"session_id": session_id})
        conn.commit()

def clear_all_sessions():
    """Xóa tất cả sessions (dùng cẩn thận!)"""
    engine = get_postgres_engine()
    
    delete_sql = text("TRUNCATE TABLE chat_history")
    
    with engine.connect() as conn:
        conn.execute(delete_sql)
        conn.commit()
