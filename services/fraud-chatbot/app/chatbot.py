"""
Fraud Detection Chatbot - Gemini + LangChain + Trino
Tính năng:
- Chat với database bằng ngôn ngữ tự nhiên
- Lưu lịch sử chat vào PostgreSQL
- Kết nối Trino Delta Lake
- Sử dụng Gemini API (FREE tier)
"""

import streamlit as st
import os
from datetime import datetime
from sqlalchemy import create_engine, text
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits import create_sql_agent
from langchain.schema import HumanMessage, AIMessage
import pandas as pd

# ============================================================
# CONFIGURATION
# ============================================================

# Gemini API Key
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")

# Trino connection
TRINO_HOST = os.getenv("TRINO_HOST", "trino")
TRINO_PORT = os.getenv("TRINO_PORT", "8081")
TRINO_USER = os.getenv("TRINO_USER", "admin")
TRINO_CATALOG = os.getenv("TRINO_CATALOG", "delta")
TRINO_SCHEMA = os.getenv("TRINO_SCHEMA", "gold")

# PostgreSQL for chat history
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "postgres")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB = os.getenv("POSTGRES_DB", "frauddb")
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")

# ============================================================
# DATABASE CONNECTIONS
# ============================================================

# KHÔNG cache để tránh lỗi 401 từ connection cũ
def get_trino_db():
    """Kết nối Trino Delta Lake"""
    from sqlalchemy import create_engine
    from sqlalchemy.pool import NullPool
    
    # Build URI với username từ environment variable
    trino_uri = f"trino://{TRINO_USER}@{TRINO_HOST}:{TRINO_PORT}/{TRINO_CATALOG}/{TRINO_SCHEMA}"
    
    # Tạo engine đơn giản - username đã có trong URI
    engine = create_engine(
        trino_uri,
        connect_args={"http_scheme": "http"},
        poolclass=NullPool,
        echo=False
    )
    
    # Tạo SQLDatabase - Không dùng include_tables vì Trino reflection có vấn đề
    # LangChain sẽ tự discover tất cả tables trong schema
    db = SQLDatabase(
        engine,
        sample_rows_in_table_info=0,
        # Bỏ include_tables - để LangChain query information_schema tự động
    )
    return db

@st.cache_resource
def get_postgres_engine():
    """Kết nối PostgreSQL cho lưu chat history"""
    postgres_uri = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
    engine = create_engine(postgres_uri)
    return engine

@st.cache_resource
def get_llm():
    """Khởi tạo Gemini LLM"""
    if not GOOGLE_API_KEY:
        st.error("⚠️ GOOGLE_API_KEY chưa được cấu hình!")
        st.stop()
    
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash-lite",
        temperature=0,
        google_api_key=GOOGLE_API_KEY,
        convert_system_message_to_human=True  # Gemini yêu cầu
    )
    return llm

@st.cache_resource
def get_sql_agent():
    """Tạo SQL Agent - AI biết query database"""
    from langchain_community.agent_toolkits import SQLDatabaseToolkit
    
    db = get_trino_db()
    llm = get_llm()
    
    # Tạo toolkit (phiên bản mới yêu cầu)
    toolkit = SQLDatabaseToolkit(db=db, llm=llm)
    
    # Tạo agent với toolkit
    agent = create_sql_agent(
        llm=llm,
        toolkit=toolkit,
        verbose=True,
        handle_parsing_errors=True
    )
    return agent

# ============================================================
# CHAT HISTORY MANAGEMENT
# ============================================================

def init_chat_history_table():
    """Tạo bảng lưu lịch sử chat nếu chưa có"""
    engine = get_postgres_engine()
    
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS chat_history (
        id SERIAL PRIMARY KEY,
        session_id VARCHAR(100) NOT NULL,
        role VARCHAR(20) NOT NULL,  -- 'user' or 'assistant'
        message TEXT NOT NULL,
        sql_query TEXT,  -- SQL query được sinh ra (nếu có)
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    
    CREATE INDEX IF NOT EXISTS idx_session_id ON chat_history(session_id);
    CREATE INDEX IF NOT EXISTS idx_created_at ON chat_history(created_at);
    """
    
    with engine.connect() as conn:
        conn.execute(text(create_table_sql))
        conn.commit()

def save_message(session_id: str, role: str, message: str, sql_query: str = None):
    """Lưu message vào PostgreSQL"""
    engine = get_postgres_engine()
    
    insert_sql = """
    INSERT INTO chat_history (session_id, role, message, sql_query)
    VALUES (:session_id, :role, :message, :sql_query)
    """
    
    with engine.connect() as conn:
        conn.execute(text(insert_sql), {
            "session_id": session_id,
            "role": role,
            "message": message,
            "sql_query": sql_query
        })
        conn.commit()

def load_chat_history(session_id: str, limit: int = 50):
    """Load lịch sử chat từ PostgreSQL"""
    engine = get_postgres_engine()
    
    query_sql = """
    SELECT role, message, sql_query, created_at
    FROM chat_history
    WHERE session_id = :session_id
    ORDER BY created_at ASC
    LIMIT :limit
    """
    
    with engine.connect() as conn:
        result = conn.execute(text(query_sql), {
            "session_id": session_id,
            "limit": limit
        })
        return result.fetchall()

def get_all_sessions():
    """Lấy danh sách tất cả sessions"""
    engine = get_postgres_engine()
    
    query_sql = """
    SELECT DISTINCT session_id, 
           MAX(created_at) as last_activity,
           COUNT(*) as message_count
    FROM chat_history
    GROUP BY session_id
    ORDER BY last_activity DESC
    LIMIT 20
    """
    
    with engine.connect() as conn:
        result = conn.execute(text(query_sql))
        return result.fetchall()

def delete_session(session_id: str):
    """Xóa session"""
    engine = get_postgres_engine()
    
    delete_sql = "DELETE FROM chat_history WHERE session_id = :session_id"
    
    with engine.connect() as conn:
        conn.execute(text(delete_sql), {"session_id": session_id})
        conn.commit()

# ============================================================
# STREAMLIT UI
# ============================================================

def init_session_state():
    """Khởi tạo session state"""
    if "session_id" not in st.session_state:
        st.session_state.session_id = f"chat_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    if "db_connected" not in st.session_state:
        st.session_state.db_connected = False

def load_session_messages(session_id: str):
    """Load messages từ database vào session state"""
    history = load_chat_history(session_id)
    st.session_state.messages = []
    
    for row in history:
        role, message, sql_query, created_at = row
        st.session_state.messages.append({
            "role": role,
            "content": message,
            "sql_query": sql_query,
            "timestamp": created_at
        })

def main():
    """Main chatbot UI"""
    
    # Page config
    st.set_page_config(
        page_title="Fraud Detection Chatbot",
        page_icon="🕵️",  # Detective emoji
        layout="wide"
    )
    
    # Initialize
    init_session_state()
    init_chat_history_table()
    
    # Sidebar
    with st.sidebar:
        st.title("🕵️ Fraud Chatbot")
        st.markdown("---")
        
        # API Key status
        if GOOGLE_API_KEY:
            st.success("✅ Gemini API Connected")
        else:
            st.error("❌ GOOGLE_API_KEY chưa cấu hình")
            st.info("Thêm vào docker-compose.yml:\n```yaml\nenvironment:\n  GOOGLE_API_KEY: AIzaSy...\n```")
        
        st.markdown("---")
        
        # Session management
        st.subheader("📝 Quản lý Sessions")
        
        # New chat button
        if st.button("➕ Chat mới", use_container_width=True):
            st.session_state.session_id = f"chat_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            st.session_state.messages = []
            st.rerun()
        
        # Load existing sessions
        sessions = get_all_sessions()
        
        if sessions:
            st.markdown("**Sessions gần đây:**")
            for session_id, last_activity, msg_count in sessions:
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    if st.button(
                        f"💬 {session_id[:20]}... ({msg_count} msgs)",
                        key=f"load_{session_id}",
                        use_container_width=True
                    ):
                        st.session_state.session_id = session_id
                        load_session_messages(session_id)
                        st.rerun()
                
                with col2:
                    if st.button("🗑️", key=f"del_{session_id}"):
                        delete_session(session_id)
                        st.rerun()
        
        st.markdown("---")
        
        # Database info
        st.subheader("🗄️ Database Info")
        st.info(f"""
        **Trino Catalog:** {TRINO_CATALOG}  
        **Schema:** {TRINO_SCHEMA}  
        **Tables:** 5 base + 9 views
        """)
        
        # Test connection
        if st.button("🔌 Test Connection"):
            try:
                # Test bằng query trực tiếp, KHÔNG dùng get_usable_table_names() (gây lỗi 401)
                from sqlalchemy import create_engine, text
                
                trino_uri = f"trino://{TRINO_USER}@{TRINO_HOST}:{TRINO_PORT}/{TRINO_CATALOG}/{TRINO_SCHEMA}"
                engine = create_engine(
                    trino_uri,
                    connect_args={"http_scheme": "http"}
                )
                
                # Query đơn giản để test
                with engine.connect() as conn:
                    result = conn.execute(text("SELECT COUNT(*) as total FROM fact_transactions"))
                    count = result.fetchone()[0]
                
                st.success(f"✅ Kết nối thành công!\n\n**Fact Transactions:** {count:,} records")
                st.session_state.db_connected = True
            except Exception as e:
                st.error(f"❌ Lỗi kết nối: {str(e)}")
                import traceback
                with st.expander("🔍 Chi tiết lỗi"):
                    st.code(traceback.format_exc())
        
        # Clear cache button
        st.markdown("---")
        if st.button("🗑️ Clear Cache", use_container_width=True):
            st.cache_resource.clear()
            st.success("✅ Cache đã xóa! Nhấn Ctrl+R để reload.")
            st.rerun()
        
        st.markdown("---")
        
        # Example queries
        with st.expander("💡 Câu hỏi mẫu"):
            st.markdown("""
            - Có bao nhiêu giao dịch gian lận hôm nay?
            - Top 5 bang có tỷ lệ gian lận cao nhất?
            - Hiển thị fraud rate theo từng giờ
            - Merchant nào nguy hiểm nhất?
            - Tổng số tiền bị gian lận tuần này?
            - Phân tích fraud patterns theo amount
            - Category nào rủi ro nhất?
            - Giao dịch gian lận gần đây nhất?
            """)
    
    # Main chat area
    st.title("💬 Fraud Detection Chatbot")
    st.caption(f"Session: `{st.session_state.session_id}`")
    
    # Display chat messages
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            
            # Show SQL query if available
            if msg.get("sql_query"):
                with st.expander("🔍 SQL Query"):
                    st.code(msg["sql_query"], language="sql")
    
    # Chat input
    if prompt := st.chat_input("Hỏi gì đó về fraud detection..."):
        # Add user message
        st.session_state.messages.append({
            "role": "user",
            "content": prompt,
            "sql_query": None
        })
        
        # Save to database
        save_message(st.session_state.session_id, "user", prompt)
        
        # Display user message
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Get AI response
        with st.chat_message("assistant"):
            with st.spinner("🤔 Đang suy nghĩ..."):
                try:
                    agent = get_sql_agent()
                    
                    # System instruction với schema chính xác từ Trino
                    system_instruction = """
                    Bạn là chuyên gia phân tích gian lận tài chính. Trả lời bằng tiếng Việt.
                    
                    THUẬT NGỮ TIẾNG VIỆT:
                    - bang/tiểu bang = state
                    - gian lận = fraud (is_fraud=1)
                    - giao dịch = transaction
                    - khách hàng = customer
                    - nhà bán hàng/merchant = merchant
                    
                    GIẢI THÍCH CÁC TRƯỜNG DỮ LIỆU QUAN TRỌNG:
                    
                    ** AMOUNT BIN (Khoảng giá trị giao dịch) **
                    - amount_bin: Chia giao dịch theo giá trị (1-5)
                      * Bin 1: $0 - $50 (giao dịch nhỏ, fraud rate thấp ~0.24%)
                      * Bin 2: $50 - $150 (fraud rate ~0.52%)
                      * Bin 3: $150 - $300 (fraud rate ~0.04%)
                      * Bin 4: $300 - $500 (fraud rate ~1.59%)
                      * Bin 5: >$500 (giao dịch lớn, fraud rate CAO NHẤT 32.26%)
                    
                    ** CATEGORY (Loại giao dịch) **
                    Có 14 categories, ví dụ:
                    - shopping_net, shopping_pos
                    - grocery_net, grocery_pos
                    - gas_transport
                    - misc_net, misc_pos
                    - entertainment, food_dining
                    - personal_care, health_fitness
                    - travel, home
                    
                    ** TIME PERIOD (Khung giờ) **
                    - time_period: 8 khung giờ trong ngày
                      * Early Morning (0-3h): Đêm khuya, nguy cơ cao
                      * Late Night (3-6h): Rất đêm, nguy cơ cao
                      * Morning (6-9h): Sáng sớm
                      * Mid Morning (9-12h): Buổi sáng
                      * Afternoon (12-15h): Chiều
                      * Late Afternoon (15-18h): Chiều muộn
                      * Evening (18-21h): Tối
                      * Night (21-24h): Đêm
                    
                    ** DAY OF WEEK (Ngày trong tuần) **
                    - transaction_day_of_week hoặc day_of_week:
                      * 0 = Thứ Hai (Monday)
                      * 1 = Thứ Ba (Tuesday)
                      * 2 = Thứ Tư (Wednesday)
                      * 3 = Thứ Năm (Thursday)
                      * 4 = Thứ Sáu (Friday)
                      * 5 = Thứ Bảy (Saturday)
                      * 6 = Chủ Nhật (Sunday)
                    
                    ** BOOLEAN FLAGS (Cờ đánh dấu) **
                    - is_fraud: 1 = gian lận, 0 = hợp lệ
                    - is_distant_transaction: 1 = giao dịch xa (>50km từ địa chỉ khách hàng)
                    - is_late_night: 1 = giao dịch đêm khuya (23h-6h)
                    - is_weekend_transaction: 1 = cuối tuần (Thứ 7, Chủ Nhật)
                    - is_high_amount: 1 = giao dịch giá trị cao (>$500)
                    - is_zero_amount: 1 = giao dịch $0 (đáng ngờ)
                    
                    ** DISTANCE (Khoảng cách) **
                    - distance_km: Khoảng cách từ địa chỉ khách hàng đến merchant
                      * <10km: Bình thường
                      * 10-50km: Xa một chút
                      * >50km: Rất xa, đáng ngờ (is_distant_transaction=1)
                    
                    ** AGE (Tuổi) **
                    - customer_age_at_transaction: Tuổi khách hàng khi giao dịch
                    - age (trong dim_customer): Tuổi hiện tại của khách hàng
                    
                    === DATABASE SCHEMA (14 tables) ===
                    
                    ** FACT TABLE (Bảng chính) **
                    fact_transactions:
                      - transaction_key (PK)
                      - customer_key → JOIN dim_customer
                      - merchant → JOIN dim_merchant (by merchant name)
                      - time_key → JOIN dim_time
                      - is_fraud (0=sạch, 1=gian lận)
                      - transaction_amount, transaction_category
                      - distance_km, customer_age_at_transaction
                      - transaction_timestamp, transaction_hour, transaction_day_of_week
                      - is_distant_transaction, is_late_night, is_weekend_transaction
                      
                    ** DIMENSION TABLES **
                    dim_customer (912 rows):
                      - customer_key (PK)
                      - customer_state, customer_city, customer_zip ← Dùng để lấy STATE
                      - first_name, last_name, gender, age, job
                      - customer_lat, customer_long
                      
                    dim_merchant (50,400 rows):
                      - merchant (tên merchant - dùng JOIN với fact_transactions.merchant)
                      - merchant_category
                      - merchant_lat, merchant_long
                      
                    dim_time (702 rows):
                      - time_key (PK)
                      - year, month, day, hour, minute
                      - day_of_week, is_weekend, time_period
                      - day_name, month_name
                      
                    dim_location (901 rows):
                      - state, city, zip
                      - lat, long, city_pop
                      
                    ** PRE-AGGREGATED VIEWS (Đã tính sẵn - query nhanh) **
                    state_summary (50 states):
                      - state, total_transactions, fraud_transactions
                      - avg_amount, avg_distance, fraud_rate
                      → Dùng này cho câu hỏi "Top 5 bang..."
                      
                    daily_summary (30 days):
                      - report_date, total_transactions, fraud_transactions
                      - avg_transaction_amount, total_amount, fraud_amount, fraud_rate
                      
                    hourly_summary (702 hours):
                      - year, month, day, hour
                      - total_transactions, fraud_transactions, fraud_rate
                      
                    category_summary (14 categories):
                      - category, total_transactions, fraud_transactions, fraud_rate
                      
                    merchant_analysis (100 merchants):
                      - merchant, merchant_category
                      - total_transactions, fraud_transactions, fraud_rate
                      → Dùng này cho câu "Merchant nguy hiểm nhất"
                      
                    amount_summary (5 ranges):
                      - amount_range, fraud_rate
                      
                    fraud_patterns (5 patterns):
                      - amount_bin (1-5, xem GIẢI THÍCH ở trên)
                      - fraud_count, avg_fraud_amount
                      → QUAN TRỌNG: Bin 5 (>$500) có fraud_rate 32% - CAO NHẤT!
                      
                    time_period_analysis (8 periods):
                      - time_period (morning/afternoon/...), fraud_rate
                      
                    latest_metrics (1 row - metrics hôm nay):
                      - total_transactions_today, fraud_detected_today
                      - fraud_rate_today, alert_level
                    
                    === CÁCH QUERY HIỆU QUẢ ===
                    1. Câu hỏi về STATE/BANG:
                       - NHANH: SELECT * FROM state_summary ORDER BY fraud_rate DESC LIMIT 5
                       - CHẬM: JOIN fact_transactions với dim_customer
                       
                    2. Câu hỏi về MERCHANT:
                       - NHANH: SELECT * FROM merchant_analysis ORDER BY fraud_rate DESC LIMIT 10
                       - CHẬM: JOIN fact_transactions với dim_merchant
                       
                    3. Câu hỏi về THỜI GIAN:
                       - Theo ngày: daily_summary
                       - Theo giờ: hourly_summary
                       - Theo time period: time_period_analysis
                       
                    4. Metrics tổng quan: latest_metrics
                    
                    QUAN TRỌNG:
                    - Ưu tiên dùng views đã tính sẵn (nhanh hơn 10-100x)
                    - Chỉ JOIN fact_transactions khi cần chi tiết cụ thể
                    - Format số đẹp, dễ đọc
                    
                    KHI TRẢ LỜI:
                    - Luôn GIẢI THÍCH ý nghĩa của các bin/code (amount_bin, time_period, etc.)
                    - Ví dụ: "Bin 5 (giao dịch >$500)" THAY VÌ chỉ "Bin 5"
                    - Đưa ra INSIGHT cụ thể: "Giao dịch lớn trên $500 có nguy cơ gian lận 32%, cao gấp 10 lần so với giao dịch nhỏ"
                    - Format số với phần trăm: "32.26%" thay vì "0.3226"
                    
                    TẠO BINS ĐỘNG (khi user yêu cầu chia bin khác):
                    Nếu user muốn chia bin khác (ví dụ: "chia 10 bin", "nhóm thành 8 khoảng"):
                    - Dùng NTILE() hoặc WIDTH_BUCKET() trong SQL để tạo bins động
                    - Ví dụ chia transaction_amount thành 10 bins:
                      ```sql
                      SELECT 
                        NTILE(10) OVER (ORDER BY transaction_amount) as amount_bin_10,
                        MIN(transaction_amount) as min_amount,
                        MAX(transaction_amount) as max_amount,
                        COUNT(*) as total_transactions,
                        SUM(is_fraud) as fraud_transactions,
                        CAST(SUM(is_fraud) AS DOUBLE) / COUNT(*) as fraud_rate
                      FROM fact_transactions
                      GROUP BY NTILE(10) OVER (ORDER BY transaction_amount)
                      ORDER BY amount_bin_10
                      ```
                    - Luôn hiển thị khoảng giá trị (min-max) cho mỗi bin mới
                    - Giải thích ý nghĩa: "Bin 1 ($0.18-$2.85): giao dịch rất nhỏ, fraud rate 0.1%"
                    """
                    
                    full_prompt = f"{system_instruction}\n\nCâu hỏi: {prompt}"
                    
                    # Capture agent output
                    import io
                    import sys
                    import re
                    
                    # Redirect stdout để capture verbose output
                    old_stdout = sys.stdout
                    sys.stdout = captured_output = io.StringIO()
                    
                    try:
                        # Run agent với prompt đầy đủ
                        response = agent.invoke({"input": full_prompt})
                        
                        # Get captured output
                        thinking_text = captured_output.getvalue()
                        
                        # Strip ANSI color codes
                        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
                        thinking_text = ansi_escape.sub('', thinking_text)
                        
                    finally:
                        # Restore stdout
                        sys.stdout = old_stdout
                    
                    # Hiển thị thinking process trong expander sau khi có kết quả
                    if thinking_text:
                        with st.expander("🧠 AI Thinking Process (Click để xem)", expanded=False):
                            st.code(thinking_text, language="text")
                    
                    # Extract answer and SQL
                    answer = response.get("output", "Xin lỗi, tôi không hiểu câu hỏi.")
                    
                    # Try to extract SQL from intermediate steps
                    sql_query = None
                    if "intermediate_steps" in response:
                        for step in response["intermediate_steps"]:
                            if isinstance(step, tuple) and len(step) > 0:
                                action = step[0]
                                if hasattr(action, "tool_input"):
                                    tool_input = action.tool_input
                                    if isinstance(tool_input, dict) and "query" in tool_input:
                                        sql_query = tool_input["query"]
                                        break
                    
                    # Display answer
                    st.markdown(answer)
                    
                    # Show SQL if found
                    if sql_query:
                        with st.expander("🔍 SQL Query"):
                            st.code(sql_query, language="sql")
                    
                    # Save to session and database
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": answer,
                        "sql_query": sql_query
                    })
                    
                    save_message(
                        st.session_state.session_id,
                        "assistant",
                        answer,
                        sql_query
                    )
                    
                except Exception as e:
                    error_msg = f"❌ Lỗi: {str(e)}"
                    st.error(error_msg)
                    
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": error_msg,
                        "sql_query": None
                    })
                    
                    save_message(
                        st.session_state.session_id,
                        "assistant",
                        error_msg
                    )

if __name__ == "__main__":
    main()
