"""
Config Loader - Load prompts và business rules từ YAML files
"""

import os
import yaml
from typing import Dict, Any
from pathlib import Path

class ConfigLoader:
    """Load configuration từ YAML files"""
    
    def __init__(self, config_dir: str = None):
        if config_dir is None:
            # Default: services/fraud-chatbot/config
            current_file = Path(__file__).resolve()
            self.config_dir = current_file.parent.parent.parent / "config"
        else:
            self.config_dir = Path(config_dir)
        
        self.prompts = None
        self.business_rules = None
    
    def load_prompts(self) -> Dict[str, Any]:
        """Load prompts.yaml"""
        if self.prompts is None:
            prompts_file = self.config_dir / "prompts.yaml"
            with open(prompts_file, 'r', encoding='utf-8') as f:
                self.prompts = yaml.safe_load(f)
        return self.prompts
    
    def load_business_rules(self) -> Dict[str, Any]:
        """Load business_rules.yaml"""
        if self.business_rules is None:
            rules_file = self.config_dir / "business_rules.yaml"
            with open(rules_file, 'r', encoding='utf-8') as f:
                self.business_rules = yaml.safe_load(f)
        return self.business_rules
    
    def get_system_prompt(self) -> str:
        """Lấy system prompt template"""
        prompts = self.load_prompts()
        return prompts.get("system_prompt", "")
    
    def get_tool_description(self, tool_name: str) -> str:
        """Lấy mô tả của một tool"""
        prompts = self.load_prompts()
        tool_descriptions = prompts.get("tool_descriptions", {})
        return tool_descriptions.get(tool_name, "")
    
    def get_risk_threshold(self, level: str) -> float:
        """Lấy ngưỡng risk"""
        rules = self.load_business_rules()
        thresholds = rules.get("risk_thresholds", {})
        return thresholds.get(f"{level}_risk", 0.5)
    
    def get_risk_emoji(self, risk_level: str) -> str:
        """Lấy emoji cho risk level"""
        rules = self.load_business_rules()
        emojis = rules.get("response_format", {}).get("risk_emojis", {})
        return emojis.get(risk_level, "")
    
    def get_risk_message(self, risk_level: str) -> str:
        """Lấy message cho risk level"""
        rules = self.load_business_rules()
        messages = rules.get("response_format", {}).get("risk_messages", {})
        return messages.get(risk_level, "")
    
    def get_recommendations(self, risk_level: str) -> list:
        """Lấy khuyến nghị cho risk level"""
        rules = self.load_business_rules()
        recommendations = rules.get("recommendations", {})
        return recommendations.get(risk_level, [])
    
    def get_amount_threshold(self, threshold_type: str) -> float:
        """Lấy ngưỡng amount"""
        rules = self.load_business_rules()
        thresholds = rules.get("amount_thresholds", {})
        return thresholds.get(threshold_type, 0)


# Singleton
_config_loader = None

def get_config_loader() -> ConfigLoader:
    """Get or create config loader singleton"""
    global _config_loader
    if _config_loader is None:
        _config_loader = ConfigLoader()
    return _config_loader


if __name__ == "__main__":
    # Test
    loader = ConfigLoader()
    
    print("=== SYSTEM PROMPT ===")
    print(loader.get_system_prompt()[:200] + "...")
    
    print("\n=== RISK THRESHOLDS ===")
    print(f"High risk: {loader.get_risk_threshold('high')}")
    print(f"Medium risk: {loader.get_risk_threshold('medium')}")
    
    print("\n=== RISK MESSAGES ===")
    print(f"HIGH: {loader.get_risk_emoji('HIGH')} {loader.get_risk_message('HIGH')}")
    print(f"MEDIUM: {loader.get_risk_emoji('MEDIUM')} {loader.get_risk_message('MEDIUM')}")
    print(f"LOW: {loader.get_risk_emoji('LOW')} {loader.get_risk_message('LOW')}")
