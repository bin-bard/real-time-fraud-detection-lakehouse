"""
Dynamic Schema Loader - Tự động đọc schema từ Trino Delta Lake
Thay vì hardcode schema trong prompt, module này query Trino để lấy schema thực tế

FEATURES:
- Auto-discover tables và views từ Trino
- Caching để tránh query Trino mỗi lần (TTL: 5 minutes)
- Priority tables để hiển thị trước
"""

import os
from typing import Dict, List, Optional
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool
import logging
import time
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class TrinoSchemaLoader:
    """Load database schema động từ Trino với caching"""
    
    def __init__(
        self,
        host: str = None,
        port: str = None,
        user: str = None,
        catalog: str = None,
        schema: str = None,
        cache_ttl_seconds: int = 300  # Cache 5 minutes
    ):
        self.host = host or os.getenv("TRINO_HOST", "trino")
        self.port = port or os.getenv("TRINO_PORT", "8081")
        self.user = user or os.getenv("TRINO_USER", "admin")
        self.catalog = catalog or os.getenv("TRINO_CATALOG", "delta")
        self.schema = schema or os.getenv("TRINO_SCHEMA", "gold")
        self.cache_ttl = cache_ttl_seconds
        
        # Cache storage
        self._cache = {}
        self._cache_timestamps = {}
        
        # Create engine
        trino_uri = f"trino://{self.user}@{self.host}:{self.port}/{self.catalog}/{self.schema}"
        self.engine = create_engine(
            trino_uri,
            connect_args={"http_scheme": "http"},
            poolclass=NullPool,
            echo=False
        )
    
    def _is_cache_valid(self, key: str) -> bool:
        """Check if cached data is still valid"""
        if key not in self._cache or key not in self._cache_timestamps:
            return False
        
        cache_time = self._cache_timestamps[key]
        elapsed = (datetime.now() - cache_time).total_seconds()
        return elapsed < self.cache_ttl
    
    def _set_cache(self, key: str, value: any):
        """Store data in cache with timestamp"""
        self._cache[key] = value
        self._cache_timestamps[key] = datetime.now()
        logger.debug(f"Cached '{key}' with TTL {self.cache_ttl}s")
    
    def _get_cache(self, key: str) -> Optional[any]:
        """Get cached data if valid"""
        if self._is_cache_valid(key):
            logger.debug(f"Cache HIT for '{key}'")
            return self._cache[key]
        logger.debug(f"Cache MISS for '{key}'")
        return None
    
    def clear_cache(self):
        """Clear all cached data (useful for testing)"""
        self._cache.clear()
        self._cache_timestamps.clear()
        logger.info("Schema cache cleared")
    
    def get_tables(self) -> List[str]:
        """Lấy danh sách tất cả tables trong schema (with caching)"""
        cache_key = f"tables_{self.catalog}_{self.schema}"
        
        # Check cache first
        cached = self._get_cache(cache_key)
        if cached is not None:
            logger.debug(f"Cache HIT for {cache_key}")
            return cached
        
        logger.info(f"Cache MISS for {cache_key} - querying Trino...")
        
        # Query Trino
        try:
            with self.engine.connect() as conn:
                query = text(f"""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = '{self.schema}'
                    ORDER BY table_name
                """)
                result = conn.execute(query)
                tables = [row[0] for row in result]
                
                logger.info(f"Loaded {len(tables)} tables from {self.catalog}.{self.schema}")
                
                # Cache result
                self._set_cache(cache_key, tables)
                return tables
        except Exception as e:
            logger.error(f"Error fetching tables: {e}")
            return []
    
    def get_table_schema(self, table_name: str) -> List[Dict[str, str]]:
        """Lấy schema (columns) của một table (with caching)"""
        cache_key = f"schema_{self.catalog}_{self.schema}_{table_name}"
        
        # Check cache
        cached = self._get_cache(cache_key)
        if cached is not None:
            logger.debug(f"Cache HIT for {cache_key}")
            return cached
        
        logger.info(f"Cache MISS for {cache_key} - querying Trino...")
        
        try:
            with self.engine.connect() as conn:
                query = text(f"""
                    SELECT column_name, data_type, is_nullable
                    FROM information_schema.columns
                    WHERE table_schema = '{self.schema}'
                      AND table_name = '{table_name}'
                    ORDER BY ordinal_position
                """)
                result = conn.execute(query)
                columns = [
                    {
                        "name": row[0],
                        "type": row[1],
                        "nullable": row[2] == "YES"
                    }
                    for row in result
                ]
                logger.info(f"Table {table_name} has {len(columns)} columns")
                
                # Cache result
                self._set_cache(cache_key, columns)
                return columns
        except Exception as e:
            logger.error(f"Error fetching schema for {table_name}: {e}")
            return []
    
    def get_table_sample(self, table_name: str, limit: int = 3) -> List[Dict]:
        """Lấy sample rows từ table để hiểu dữ liệu"""
        try:
            with self.engine.connect() as conn:
                query = text(f"SELECT * FROM {self.catalog}.{self.schema}.{table_name} LIMIT {limit}")
                result = conn.execute(query)
                rows = [dict(row._mapping) for row in result]
                return rows
        except Exception as e:
            logger.error(f"Error fetching sample from {table_name}: {e}")
            return []
    
    def get_complete_schema_info(self, include_samples: bool = False) -> Dict[str, any]:
        """Lấy toàn bộ thông tin schema cho tất cả tables"""
        schema_info = {}
        tables = self.get_tables()
        
        for table_name in tables:
            columns = self.get_table_schema(table_name)
            table_info = {
                "columns": columns,
                "column_count": len(columns)
            }
            
            if include_samples:
                table_info["sample_data"] = self.get_table_sample(table_name)
            
            schema_info[table_name] = table_info
        
        return schema_info
    
    def format_schema_for_prompt(self, prioritize_tables: Optional[List[str]] = None) -> str:
        """
        Format schema thành string để inject vào prompt
        
        Args:
            prioritize_tables: Danh sách tables quan trọng sẽ được hiển thị đầu tiên
        """
        cache_key = "formatted_schema"
        
        # Check cache
        cached = self._get_cache(cache_key)
        if cached is not None:
            return cached
        
        schema_info = self.get_complete_schema_info(include_samples=False)
        
        if not schema_info:
            return "⚠️ Không thể load schema từ Trino"
        
        # Priority tables - UPDATED: All views from gold_layer_views_delta.sql
        priority_tables = prioritize_tables or [
            # Pre-aggregated views (FAST)
            "state_summary",
            "merchant_analysis", 
            "category_summary",
            "amount_summary",
            "hourly_summary",
            "daily_summary",
            "latest_metrics",
            "fraud_patterns",
            "time_period_analysis",
            # Base tables (SLOWER)
            "fact_transactions",
            "dim_customer",
            "dim_merchant",
            "dim_time",
            "dim_location"
        ]
        
        formatted = []
        
        # Format priority tables first
        formatted.append("**📊 Bảng Pre-Aggregated (Ưu tiên - Nhanh):**\n")
        aggregated_views = ["state_summary", "merchant_analysis", "category_summary", 
                           "amount_summary", "hourly_summary", "daily_summary", 
                           "latest_metrics", "fraud_patterns", "time_period_analysis"]
        
        for table_name in priority_tables:
            if table_name in schema_info and table_name in aggregated_views:
                info = schema_info[table_name]
                columns = info["columns"]
                col_names = [f"{col['name']} ({col['type']})" for col in columns[:8]]  # Limit to 8 cols
                formatted.append(f"  - **{table_name}**: {', '.join(col_names)}")
                if len(columns) > 8:
                    formatted.append(f"    ... và {len(columns) - 8} columns khác")
        
        # Format base tables
        formatted.append("\n**📋 Bảng Base (Chậm hơn - Chỉ dùng khi cần chi tiết):**\n")
        base_tables = ["fact_transactions", "dim_customer", "dim_merchant", "dim_time", "dim_location"]
        
        for table_name in base_tables:
            if table_name in schema_info:
                info = schema_info[table_name]
                formatted.append(f"  - **{table_name}**: {info['column_count']} columns")
        
        # Format other tables if any
        other_tables = [t for t in schema_info.keys() if t not in priority_tables]
        if other_tables:
            formatted.append("\n**📁 Bảng khác:**\n")
            for table_name in sorted(other_tables):
                info = schema_info[table_name]
                formatted.append(f"  - **{table_name}**: {info['column_count']} columns")
        
        result = "\n".join(formatted)
        
        # Cache result
        self._set_cache(cache_key, result)
        
        return result
    
    def get_table_description(self, table_name: str) -> str:
        """Tạo mô tả chi tiết cho một table cụ thể"""
        columns = self.get_table_schema(table_name)
        if not columns:
            return f"Table {table_name} không tồn tại hoặc không có quyền truy cập"
        
        desc = [f"**Table: {table_name}** ({len(columns)} columns)\n"]
        for col in columns:
            nullable = "NULL" if col["nullable"] else "NOT NULL"
            desc.append(f"  - {col['name']}: {col['type']} ({nullable})")
        
        return "\n".join(desc)


# Singleton instance
_schema_loader = None

def get_schema_loader(cache_ttl_seconds: int = 300) -> TrinoSchemaLoader:
    """
    Get or create schema loader singleton
    
    Args:
        cache_ttl_seconds: Cache TTL in seconds (default: 300 = 5 minutes)
    """
    global _schema_loader
    if _schema_loader is None:
        _schema_loader = TrinoSchemaLoader(cache_ttl_seconds=cache_ttl_seconds)
        logger.info(f"Schema loader initialized with cache TTL: {cache_ttl_seconds}s")
    return _schema_loader


def clear_schema_cache():
    """Clear schema cache (useful when tables/views change)"""
    global _schema_loader
    if _schema_loader is not None:
        _schema_loader.clear_cache()
        logger.info("Global schema cache cleared")


# Convenience function
def get_dynamic_schema_prompt() -> str:
    """Lấy schema đã format để inject vào prompt (with caching)"""
    loader = get_schema_loader()
    return loader.format_schema_for_prompt()


if __name__ == "__main__":
    # Test
    logging.basicConfig(level=logging.INFO)
    loader = TrinoSchemaLoader()
    
    print("=== TABLES ===")
    tables = loader.get_tables()
    print(tables)
    
    print("\n=== SCHEMA INFO ===")
    schema_prompt = loader.format_schema_for_prompt()
    print(schema_prompt)
    
    print("\n=== SAMPLE TABLE DETAIL ===")
    if tables:
        detail = loader.get_table_description(tables[0])
        print(detail)
