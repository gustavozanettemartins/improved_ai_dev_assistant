#!/usr/bin/env python3

import json
import os
import logging
import datetime
from colorama import Fore, Style

# Default configuration
DEFAULT_CONFIG = {
    "api_url": "http://localhost:11434/api/generate",
    "log_level": "INFO",
    "working_dir": "projects",
    "history_file": "dev_conversation_history.json",
    "cache_dir": ".ai_dev_cache",
    "max_history_entries": 100,
    "max_context_files": 10,
    "max_cache_size_mb": 100,
    "timeout_seconds": 60,
    "default_model": "qwen2.5-coder:14b",
    "models": {
        "qwen2.5-coder:14b": {"temperature": 0.7, "timeout": 60},
        "llama3.2:latest": {"temperature": 0.8, "timeout": 60},
        "claude3-haiku:latest": {"temperature": 0.7, "timeout": 120},
        "mixtral:latest": {"temperature": 0.8, "timeout": 90}
    },
    "supported_languages": ["python", "javascript", "typescript", "java", "go", "rust"],
    "enable_telemetry": False,
    "auto_save_interval": 300,  # 5 minutes
    "enable_web_interface": False,
    "web_interface_port": 8080,
    "git_integration": False,
    "dependency_check": True,
    "code_quality_checks": True,
    "backup_files": True
}

class ConfigManager:
    """Manages configuration settings with file I/O and validation."""
    
    def __init__(self, config_file: str = "ai_dev_config.json"):
        self.config_file = config_file
        self.config = self._load_config()
        self._setup_logging()
        self._validate_config()
        self._ensure_directories()

    def _load_config(self) -> dict:
        """Load configuration from file or use defaults."""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    user_config = json.load(f)
                    # Deep merge with defaults
                    config = DEFAULT_CONFIG.copy()
                    self._deep_update(config, user_config)
                    return config
        except Exception as e:
            print(f"Error loading config: {e}, using defaults")
        return DEFAULT_CONFIG.copy()
    
    def _deep_update(self, d: dict, u: dict) -> dict:
        """Recursively update a dict."""
        for k, v in u.items():
            if isinstance(v, dict) and k in d and isinstance(d[k], dict):
                self._deep_update(d[k], v)
            else:
                d[k] = v
        return d
    
    def _setup_logging(self) -> None:
        """Configure logging based on settings."""
        log_level = getattr(logging, self.config["log_level"], logging.INFO)
        log_dir = os.path.join(self.config["working_dir"], "logs")
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, f"ai_dev_assistant_{datetime.datetime.now().strftime('%Y%m%d')}.log")
        
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger("AI-Dev-Assistant")
        self.logger.info(f"Logging initialized at level {self.config['log_level']}")
    
    def _validate_config(self) -> None:
        """Validate the configuration settings."""
        # Check required settings
        required_keys = ["api_url", "working_dir", "history_file", "default_model"]
        missing = [key for key in required_keys if key not in self.config]
        if missing:
            self.logger.warning(f"Missing required config keys: {missing}, using defaults")
            for key in missing:
                if key in DEFAULT_CONFIG:
                    self.config[key] = DEFAULT_CONFIG[key]
        
        # Check and normalize numeric values
        if not isinstance(self.config.get("max_history_entries", 0), int):
            self.config["max_history_entries"] = int(DEFAULT_CONFIG["max_history_entries"])
        
        # Validate URLs
        if not self.config["api_url"].startswith(("http://", "https://")):
            self.logger.warning(f"Invalid API URL: {self.config['api_url']}, using default")
            self.config["api_url"] = DEFAULT_CONFIG["api_url"]
    
    def _ensure_directories(self) -> None:
        """Ensure required directories exist."""
        dirs = [
            self.config["working_dir"],
            os.path.join(self.config["working_dir"], "templates"),
            self.config["cache_dir"]
        ]
        for d in dirs:
            os.makedirs(d, exist_ok=True)
            self.logger.debug(f"Ensured directory exists: {d}")
    
    def save_config(self) -> None:
        """Save current configuration to file."""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2)
            self.logger.info(f"Configuration saved to {self.config_file}")
        except Exception as e:
            self.logger.error(f"Error saving config: {e}")
    
    def get(self, key: str, default=None):
        """Get a configuration value."""
        return self.config.get(key, default)
    
    def set(self, key: str, value) -> None:
        """Set a configuration value."""
        self.config[key] = value
        self.logger.debug(f"Config updated: {key} = {value}")
    
    def print_config(self) -> None:
        """Print current configuration in a user-friendly format."""
        print(f"\n{Fore.CYAN}===== Current Configuration ====={Style.RESET_ALL}")
        for key, value in self.config.items():
            if isinstance(value, dict):
                print(f"{Fore.GREEN}{key}:{Style.RESET_ALL}")
                for subkey, subvalue in value.items():
                    print(f"  {Fore.YELLOW}{subkey}:{Style.RESET_ALL} {subvalue}")
            else:
                print(f"{Fore.GREEN}{key}:{Style.RESET_ALL} {value}")

# Initialize the global config manager instance
config_manager = ConfigManager()
logger = config_manager.logger
