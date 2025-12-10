"""
LangChain Agent cho Fraud Detection
Sử dụng ReAct pattern để tự động chọn tools

REFACTORED:
- Prompt được load từ config/prompts.yaml
- Schema được dynamic load từ Trino
- Business rules tách riêng ra config
"""

from langchain.agents import AgentExecutor, create_react_agent
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import PromptTemplate
from typing import Dict
import streamlit as st
import os
import logging

# Import tools
import sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from core.tools import create_database_tool, create_prediction_tool, create_model_info_tool
from core.config import GEMINI_MODEL_NAME, GEMINI_MAX_RETRIES, GEMINI_REQUEST_TIMEOUT
from utils.config_loader import get_config_loader
from utils.schema_loader import get_schema_loader

logger = logging.getLogger(__name__)

@st.cache_resource
def get_fraud_detection_agent() -> AgentExecutor:
    """
    Tạo ReAct Agent với dynamic schema và config-based prompts
    
    IMPROVEMENTS:
    - Prompt load từ config/prompts.yaml
    - Schema tự động load từ Trino
    - Business rules từ config/business_rules.yaml
    """
    
    # Load config và schema
    config_loader = get_config_loader()
    schema_loader = get_schema_loader()
    
    # LLM - Gemini với retry limit
    llm = ChatGoogleGenerativeAI(
        model=GEMINI_MODEL_NAME,  # Centralized config
        temperature=0,
        google_api_key=os.getenv("GOOGLE_API_KEY", ""),
        max_retries=GEMINI_MAX_RETRIES,
        request_timeout=GEMINI_REQUEST_TIMEOUT
    )
    
    # Tools
    tools = [
        create_database_tool(),
        create_prediction_tool(llm),
        create_model_info_tool()
    ]
    
    # Get dynamic schema from Trino
    try:
        logger.info("Loading dynamic schema from Trino...")
        schema_text = schema_loader.format_schema_for_prompt()
        logger.info(f"Schema loaded: {len(schema_text)} characters")
    except Exception as e:
        logger.warning(f"Failed to load dynamic schema: {e}, using fallback")
        schema_text = "⚠️ Schema loading failed - using cached knowledge"
    
    # Get prompt template from config
    system_prompt_template = config_loader.get_system_prompt()
    
    # Inject dynamic schema vào prompt
    system_prompt = system_prompt_template.format(
        tools="{tools}",  # Placeholder for LangChain
        tool_names="{tool_names}",  # Placeholder for LangChain
        database_schema=schema_text,
        input="{input}",  # Placeholder for LangChain
        agent_scratchpad="{agent_scratchpad}"  # Placeholder for LangChain
    )
    
    # Create prompt template
    prompt = PromptTemplate.from_template(system_prompt)
    
    # Create agent
    agent = create_react_agent(
        llm=llm,
        tools=tools,
        prompt=prompt
    )
    
    # Executor với error handling
    executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,
        handle_parsing_errors=True,
        max_iterations=15,  # Tăng lên để xử lý câu hỏi phức tạp và retry
        max_execution_time=60,  # Timeout 60s để tránh loop vô hạn
        return_intermediate_steps=True
    )
    
    logger.info("✅ Agent initialized with dynamic schema and config-based prompts")
    return executor

def run_agent(question: str) -> Dict:
    """Chạy agent và trả về kết quả"""
    
    agent = get_fraud_detection_agent()
    
    try:
        # Run với timeout để tránh retry vô hạn
        import signal
        
        def timeout_handler(signum, frame):
            raise TimeoutError("Agent execution timeout")
        
        # Set timeout 90s (cho phép max 2 retries của Gemini)
        # signal.alarm(90)  # Chỉ work trên Unix
        
        result = agent.invoke({"input": question})
        
        # signal.alarm(0)  # Cancel timeout
        
        return {
            "success": True,
            "answer": result.get("output", ""),
            "intermediate_steps": result.get("intermediate_steps", []),
            "sql_queries": extract_sql_queries(result.get("intermediate_steps", []))
        }
    except TimeoutError:
        return {
            "success": False,
            "error": "⏱️ Request timeout sau 90s. Có thể Gemini API đang quá tải."
        }
    except Exception as e:
        error_msg = str(e)
        
        # Check for quota exceeded error
        if "429" in error_msg or "quota" in error_msg.lower() or "ResourceExhausted" in error_msg:
            return {
                "success": False,
                "error": "⚠️ Gemini API quota exceeded (20 requests/day limit). Vui lòng thử lại sau vài phút hoặc upgrade plan tại https://ai.google.dev/pricing"
            }
        
        return {
            "success": False,
            "error": error_msg
        }

def extract_sql_queries(steps) -> list:
    """Trích xuất SQL queries từ intermediate steps"""
    queries = []
    
    for step in steps:
        if isinstance(step, tuple) and len(step) >= 2:
            action, observation = step
            
            # Check if tool was QueryDatabase
            if hasattr(action, 'tool') and action.tool == 'QueryDatabase':
                if hasattr(action, 'tool_input'):
                    # Tool input có thể là dict hoặc string
                    tool_input = action.tool_input
                    if isinstance(tool_input, dict):
                        sql = tool_input.get('sql_query', '')
                    else:
                        sql = str(tool_input)
                    
                    if sql:
                        queries.append(sql)
    
    return queries
