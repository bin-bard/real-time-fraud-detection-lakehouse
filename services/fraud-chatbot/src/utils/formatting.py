"""
Formatting Utilities
Format tiền tệ, ngày tháng, số liệu cho hiển thị
"""

from typing import Any
import pandas as pd

def format_currency(amount: float, currency: str = "USD") -> str:
    """Format số tiền thành dạng tiền tệ"""
    if currency == "USD":
        return f"${amount:,.2f}"
    elif currency == "VND":
        return f"{amount:,.0f}₫"
    else:
        return f"{amount:,.2f}"

def format_percentage(value: float, decimals: int = 1) -> str:
    """Format số thập phân thành phần trăm"""
    return f"{value * 100:.{decimals}f}%"

def format_datetime(dt: Any) -> str:
    """Format datetime thành chuỗi đẹp"""
    if isinstance(dt, str):
        dt = pd.to_datetime(dt)
    return dt.strftime("%d/%m/%Y %H:%M:%S")

def format_number(num: float, decimals: int = 2) -> str:
    """Format số với dấu phẩy ngăn cách hàng nghìn"""
    return f"{num:,.{decimals}f}"

def risk_emoji(risk_level: str) -> str:
    """Trả về emoji theo risk level"""
    mapping = {
        "LOW": "🟢",
        "MEDIUM": "🟡", 
        "HIGH": "🔴",
        "UNKNOWN": "⚪"
    }
    return mapping.get(risk_level.upper(), "⚪")

def fraud_status_icon(is_fraud: bool) -> str:
    """Icon cho fraud status"""
    return "⚠️" if is_fraud else "✅"
