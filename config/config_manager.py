#!/usr/bin/env python3

import json
import os
import logging
import uuid
from typing import Dict, Any, List, Optional, Union, Callable

# Default configuration with expanded settings
DEFAULT_CONFIG = {
    # Core settings
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
        "deepseek-r1:32b": {"temperature": 0.7, "timeout": 300},
        "qwen2.5-coder:7b": {"temperature": 0.7, "timeout": 60},
        "phi4:latest": {"temperature": 0.7, "timeout": 120},
        "llava:34b": {"temperature": 0.7, "timeout": 300}
    },
    "supported_languages": ["python", "javascript", "typescript", "java", "go", "rust"],
    "enable_telemetry": False,
    "auto_save_interval": 300,  # 5 minutes
    "enable_web_interface": False,
    "web_interface_port": 8080,
    "git_integration": False,
    "dependency_check": True,
    "code_quality_checks": True,
    "backup_files": True,

    # Expanded logging settings
    "logging": {
        "app_name": "ai_dev_assistant",
        "console_level": "INFO",
        "file_level": "DEBUG",
        "enable_json_logs": True,
        "max_log_file_size_mb": 10,
        "backup_count": 5,
        "use_console_colors": True,
        "log_directory": "logs",  # Subdirectory under working_dir
        "log_format": "%(asctime)s [%(correlation_id)s] %(levelname)s - %(name)s - %(message)s",
        "date_format": "%Y-%m-%d %H:%M:%S"
    },

    # Error handling settings
    "error_handling": {
        "default_error_mode": "log_and_raise",  # Options: log_only, log_and_raise, suppress
        "default_error_category": "unknown",  # Default error category if not specified
        "enable_error_suggestion": True,  # Provide suggestions for errors
        "max_retry_count": 3  # Maximum retry count for retryable operations
    },

    # New: Development assistant specific settings
    "dev_assistant": {
        "max_retries": 3,
        "retry_delay": 1.0,
        "file_extensions": {
            "python": ["py", "pyw"],
            "javascript": ["js", "jsx"],
            "typescript": ["ts", "tsx"],
            "html": ["html", "htm"],
            "css": ["css", "scss"],
            "markdown": ["md", "markdown"],
            "json": ["json"],
            "yaml": ["yaml", "yml"],
            "text": ["txt"]
        },
        "timeout": {
            "code_execution": 30,
            "test_execution": 60,
            "api_request": 60
        }
    },

    # New: Web search settings
    "web_search": {
        "user_agents": [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Safari/605.1.15",
            "Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/115.0"
        ],
        "domain_throttle": {
            "www.google.com": 2.0,
            "www.bing.com": 1.5,
            "html.duckduckgo.com": 1.0
        },
        "default_engine": "duckduckgo",
        "default_results": 5,
        "fallback_enabled": True,
        "fallback_engines": ["duckduckgo", "bing"],
        "max_retries": 3,
        "retry_delay": 1.0
    },

    # New: HTTP session settings
    "http_session": {
        "connection_pool_size": 20,
        "dns_cache_ttl": 300,
        "default_timeout": 30,
        "default_max_retries": 3,
        "default_retry_delay": 1.0,
        "throttle_rate": 0.5,
        "user_agent_rotation": True
    },

    # New: Model API settings
    "model_api": {
        "stream_chunk_delay": 0.1,
        "cache_chunk_size_ratio": 10,
        "retry_on_error": True,
        "show_performance_stats": True,
        "extract_json_pattern": r'(\{.*\}|\[.*\])'
    },

    # New: Code handler settings
    "code_handler": {
        "regex_patterns": {
            "python": [
                "```python\\s*(.*?)```",
                "```\\s*(.*?)```",
                "<pre><code.*?>python(.*?)</code></pre>",
                "<code language=['\"]?python['\"]?>(.*?)</code>"
            ],
            "javascript": [
                "```javascript\\s*(.*?)```",
                "```js\\s*(.*?)```",
                "```\\s*(.*?)```",
                "<pre><code.*?>javascript(.*?)</code></pre>"
            ]
        },
        "execute": {
            "safe_mode": True,
            "max_execution_time": 30,
            "allowed_imports": ["math", "datetime", "re", "json", "os.path", "random", "string"],
            "blocked_modules": ["subprocess", "socket", "requests", "urllib", "sys", "shutil"]
        },
        "backup": {
            "enabled": True,
            "directory": "backups",  # Relative to the file being modified
            "max_backups": 10
        }
    },

    # New: Cache settings
    "cache": {
        "enabled": True,
        "max_memory_items": 100,
        "eviction_policy": "lru",  # Options: lru, lfu
        "cleanup_interval": 3600,  # In seconds
        "serialize_format": "json"
    },

    # New: CLI settings
    "cli": {
        "command_aliases": {
            "h": "help",
            "q": "exit",
            "s": "search",
            "e": "edit",
            "c": "create",
            "t": "test",
            "p": "project",
            "g": "git"
        },
        "history_file": ".ai_dev_history",
        "max_history": 1000,
        "enable_colors": True
    }
}


# Improved ConfigError with better error reporting
class ConfigError(Exception):
    """Exception raised for configuration errors."""

    def __init__(self, message: str, key: Optional[str] = None, value: Any = None):
        """
        Initialize the configuration error.

        Args:
            message: Error message
            key: Optional configuration key that caused the error
            value: Optional invalid value
        """
        self.key = key
        self.value = value

        if key is not None:
            message = f"Configuration error for '{key}': {message}"
            if value is not None:
                message += f" (value: {value})"

        super().__init__(message)


class ConfigManager:
    """Manages configuration settings with file I/O, validation, and nested access."""

    def __init__(self, config_file: str = "ai_dev_config.json"):
        """
        Initialize the configuration manager.

        Args:
            config_file: Path to the configuration file
        """
        self.config_file = config_file
        self.instance_id = str(uuid.uuid4())

        # Set up basic logging until structured logging is initialized
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[logging.StreamHandler()]
        )
        self.logger = logging.getLogger("ConfigManager")

        # Load configuration (the base config will be initialized here)
        self.config = self._load_config()

        # Create required directories
        self._ensure_directories()

        # Store original config paths for potential overwrites
        self._config_paths = {
            "user_config": self.config_file,
            "working_dir": self.config.get("working_dir", "projects")
        }

        self.logger.info(f"ConfigManager initialized with file: {self.config_file}")

    def _deep_update(self, d: dict, u: dict) -> dict:
        """
        Recursively update a dictionary.

        Args:
            d: Dictionary to update
            u: Dictionary with updates

        Returns:
            Updated dictionary
        """
        for k, v in u.items():
            if isinstance(v, dict) and k in d and isinstance(d[k], dict):
                self._deep_update(d[k], v)
            else:
                d[k] = v
        return d

    def _load_config(self) -> dict:
        """
        Load configuration from file or use defaults.

        Returns:
            Loaded configuration as dictionary
        """
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    user_config = json.load(f)
                    self.logger.info(f"Loaded user configuration from {self.config_file}")

                    # Deep merge with defaults
                    config = DEFAULT_CONFIG.copy()
                    self._deep_update(config, user_config)
                    return config

        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON in config file: {e}, using defaults")
        except Exception as e:
            self.logger.error(f"Error loading config: {e}, using defaults")

        self.logger.warning("Using default configuration")
        return DEFAULT_CONFIG.copy()

    def _ensure_directories(self) -> None:
        """Ensure required directories exist."""
        dirs = [
            self.config["working_dir"],
            os.path.join(self.config["working_dir"], "templates"),
            self.config["cache_dir"],
            os.path.join(self.config["working_dir"], self.config["logging"]["log_directory"]),
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
            raise ConfigError(f"Failed to save configuration: {e}")

    def get(self, key: str, default=None):
        """
        Get a configuration value with support for nested keys.

        Args:
            key: Configuration key (can use dot notation for nested keys)
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        # Support for nested keys with dot notation
        if '.' in key:
            parts = key.split('.')
            current = self.config
            for part in parts:
                if isinstance(current, dict) and part in current:
                    current = current[part]
                else:
                    return default
            return current

        return self.config.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """
        Set a configuration value with support for nested keys.

        Args:
            key: Configuration key (can use dot notation for nested keys)
            value: Value to set
        """
        # Support for nested keys with dot notation
        if '.' in key:
            parts = key.split('.')
            current = self.config
            for part in parts[:-1]:
                if part not in current:
                    current[part] = {}
                elif not isinstance(current[part], dict):
                    current[part] = {}
                current = current[part]
            current[parts[-1]] = value
        else:
            self.config[key] = value

        self.logger.debug(f"Config updated: {key} = {value}")

    def print_config(self, section: Optional[str] = None) -> None:
        """
        Print current configuration in a user-friendly format.

        Args:
            section: Optional section to print (e.g., 'logging', 'web_search')
        """
        try:
            import colorama
            from colorama import Fore, Style
            colorama.init()

            if section:
                if section in self.config and isinstance(self.config[section], dict):
                    print(f"\n{Fore.CYAN}===== {section.upper()} Configuration ====={Style.RESET_ALL}")
                    self._print_dict_colored(self.config[section])
                else:
                    print(f"\n{Fore.RED}Section '{section}' not found in configuration{Style.RESET_ALL}")
            else:
                print(f"\n{Fore.CYAN}===== Current Configuration ====={Style.RESET_ALL}")
                self._print_dict_colored(self.config)

        except ImportError:
            print("\n===== Current Configuration =====")
            import pprint
            if section:
                if section in self.config and isinstance(self.config[section], dict):
                    pprint.pprint(self.config[section])
                else:
                    print(f"Section '{section}' not found in configuration")
            else:
                pprint.pprint(self.config)

    def _print_dict_colored(self, d: Dict, indent: int = 0, max_depth: int = 3, current_depth: int = 0) -> None:
        """
        Print a dictionary with colors and indentation.

        Args:
            d: Dictionary to print
            indent: Indentation level
            max_depth: Maximum depth to print
            current_depth: Current depth level
        """
        from colorama import Fore, Style

        indent_str = "  " * indent

        # Check if we've reached max depth
        if current_depth >= max_depth:
            remaining_keys = len(d)
            print(f"{indent_str}{Fore.YELLOW}... and {remaining_keys} more items{Style.RESET_ALL}")
            return

        for key, value in d.items():
            if isinstance(value, dict):
                print(f"{indent_str}{Fore.GREEN}{key}:{Style.RESET_ALL}")
                self._print_dict_colored(value, indent + 1, max_depth, current_depth + 1)
            elif isinstance(value, list) and len(value) > 5:
                print(f"{indent_str}{Fore.GREEN}{key}:{Style.RESET_ALL} [{len(value)} items]")
                for i, item in enumerate(value[:3]):
                    print(f"{indent_str}  {i}: {item}")
                print(f"{indent_str}  ... and {len(value) - 3} more items")
            elif isinstance(value, list):
                list_str = ", ".join(str(item) for item in value)
                print(f"{indent_str}{Fore.GREEN}{key}:{Style.RESET_ALL} [{list_str}]")
            else:
                print(f"{indent_str}{Fore.GREEN}{key}:{Style.RESET_ALL} {value}")

    def validate(self, section: Optional[str] = None) -> List[str]:
        """
        Validate the configuration or a specific section.

        Args:
            section: Optional section to validate

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        # Internal validation function
        def validate_section(section_name: str, section_data: Dict) -> None:
            if section_name == "models":
                # Validate model settings
                for model_name, model_config in section_data.items():
                    if not isinstance(model_config, dict):
                        errors.append(f"Model '{model_name}' configuration must be a dictionary")
                        continue

                    # Check temperature
                    temp = model_config.get("temperature")
                    if temp is not None and (not isinstance(temp, (int, float)) or temp < 0 or temp > 1):
                        errors.append(f"Model '{model_name}' temperature must be a number between 0 and 1")

                    # Check timeout
                    timeout = model_config.get("timeout")
                    if timeout is not None and (not isinstance(timeout, int) or timeout <= 0):
                        errors.append(f"Model '{model_name}' timeout must be a positive integer")

            elif section_name == "logging":
                # Validate logging settings
                log_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

                console_level = section_data.get("console_level")
                if console_level and console_level not in log_levels:
                    errors.append(f"Invalid console log level: {console_level}")

                file_level = section_data.get("file_level")
                if file_level and file_level not in log_levels:
                    errors.append(f"Invalid file log level: {file_level}")

                # Check numeric values
                max_size = section_data.get("max_log_file_size_mb")
                if max_size is not None and (not isinstance(max_size, int) or max_size <= 0):
                    errors.append("max_log_file_size_mb must be a positive integer")

                backup_count = section_data.get("backup_count")
                if backup_count is not None and (not isinstance(backup_count, int) or backup_count < 0):
                    errors.append("backup_count must be a non-negative integer")

            elif section_name == "web_search":
                # Validate web search settings
                engines = ["google", "bing", "duckduckgo", "ddg"]
                default_engine = section_data.get("default_engine")
                if default_engine and default_engine not in engines:
                    errors.append(f"Invalid default search engine: {default_engine}")

                user_agents = section_data.get("user_agents", [])
                if not isinstance(user_agents, list) or not all(isinstance(ua, str) for ua in user_agents):
                    errors.append("user_agents must be a list of strings")

                domain_throttle = section_data.get("domain_throttle", {})
                if not isinstance(domain_throttle, dict):
                    errors.append("domain_throttle must be a dictionary")
                else:
                    for domain, rate in domain_throttle.items():
                        if not isinstance(rate, (int, float)) or rate <= 0:
                            errors.append(f"domain_throttle[{domain}] must be a positive number")

            # Add more validation for other sections as needed

        if section:
            # Validate a specific section
            section_data = self.config.get(section)
            if section_data is None:
                errors.append(f"Section '{section}' not found in configuration")
            elif not isinstance(section_data, dict):
                errors.append(f"Section '{section}' must be a dictionary")
            else:
                validate_section(section, section_data)
        else:
            # Validate required top-level keys
            required_keys = ["api_url", "working_dir", "default_model"]
            for key in required_keys:
                if key not in self.config:
                    errors.append(f"Missing required key: {key}")

            # Validate default model
            if "default_model" in self.config and "models" in self.config:
                if self.config["default_model"] not in self.config["models"]:
                    errors.append(f"Default model '{self.config['default_model']}' not found in models")

            # Validate each section
            for section_name, section_data in self.config.items():
                if isinstance(section_data, dict):
                    validate_section(section_name, section_data)

        return errors

    def get_all(self) -> Dict[str, Any]:
        """
        Get the complete configuration dictionary.

        Returns:
            Copy of the configuration dictionary
        """
        return self.config.copy()

    def reset(self, section: Optional[str] = None) -> None:
        """
        Reset configuration to defaults.

        Args:
            section: Optional section to reset
        """
        if section:
            if section in DEFAULT_CONFIG:
                self.config[section] = DEFAULT_CONFIG[section].copy()
                self.logger.info(f"Reset configuration section: {section}")
            else:
                self.logger.warning(f"Unknown configuration section: {section}")
        else:
            self.config = DEFAULT_CONFIG.copy()
            self.logger.info("Reset configuration to defaults")

    def merge(self, config_dict: Dict[str, Any]) -> None:
        """
        Merge configuration with the given dictionary.

        Args:
            config_dict: Dictionary to merge with configuration
        """
        self._deep_update(self.config, config_dict)
        self.logger.info("Merged configuration with external dictionary")

    def get_section(self, section: str) -> Optional[Dict[str, Any]]:
        """
        Get a configuration section.

        Args:
            section: Section name

        Returns:
            Section as dictionary or None if not found
        """
        section_data = self.config.get(section)
        if isinstance(section_data, dict):
            return section_data.copy()
        return None

    def setup_structured_logging(self) -> bool:
        """
        Set up structured logging based on configuration.

        Returns:
            True if structured logging was initialized, False otherwise
        """
        # Import here to avoid circular imports
        try:
            from utils.structured_logger import setup_structured_logging

            # Get logging configuration
            logging_config = self.config.get("logging", {})

            # Set up structured logging
            log_dir = os.path.join(self.config["working_dir"], logging_config.get("log_directory", "logs"))

            result = setup_structured_logging(
                app_name=logging_config.get("app_name", "ai_dev_assistant"),
                log_dir=log_dir,
                console_level=self._get_log_level(logging_config.get("console_level", "INFO")),
                file_level=self._get_log_level(logging_config.get("file_level", "DEBUG")),
                enable_json_logs=logging_config.get("enable_json_logs", True),
                max_log_file_size=logging_config.get("max_log_file_size_mb", 10) * 1024 * 1024,
                backup_count=logging_config.get("backup_count", 5),
                use_console_colors=logging_config.get("use_console_colors", True)
            )

            # Re-acquire the logger with structured logging
            if result:
                from utils.structured_logger import get_logger
                self.logger = get_logger("ConfigManager")

                self.logger.info(
                    "Structured logging initialized",
                    extra={"structured_data": {"config_id": self.instance_id}}
                )

            return result

        except ImportError:
            self.logger.warning("Structured logging not available, using basic logging")
            return False

    def _get_log_level(self, level_name: str) -> int:
        """
        Convert a log level name to its numeric value.

        Args:
            level_name: Log level name (DEBUG, INFO, etc.)

        Returns:
            Numeric log level
        """
        levels = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
            "CRITICAL": logging.CRITICAL
        }

        return levels.get(level_name.upper(), logging.INFO)

    def export_to_file(self, filepath: str, section: Optional[str] = None) -> bool:
        """
        Export configuration to a file in JSON format.

        Args:
            filepath: Path to the export file
            section: Optional section to export

        Returns:
            True if export was successful, False otherwise
        """
        try:
            data = self.config
            if section:
                data = self.get_section(section)
                if data is None:
                    self.logger.error(f"Cannot export section '{section}': not found")
                    return False

            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)

            self.logger.info(f"Configuration exported to {filepath}")
            return True
        except Exception as e:
            self.logger.error(f"Error exporting configuration: {e}")
            return False

    def import_from_file(self, filepath: str, section: Optional[str] = None) -> bool:
        """
        Import configuration from a file in JSON format.

        Args:
            filepath: Path to the import file
            section: Optional section to import

        Returns:
            True if import was successful, False otherwise
        """
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)

            if section:
                if section not in self.config:
                    self.config[section] = {}

                self._deep_update(self.config[section], data)
                self.logger.info(f"Imported configuration section '{section}' from {filepath}")
            else:
                # Whole config import
                self._deep_update(self.config, data)
                self.logger.info(f"Imported full configuration from {filepath}")

            return True
        except Exception as e:
            self.logger.error(f"Error importing configuration: {e}")
            return False

    def get_instance_id(self) -> str:
        """
        Get the unique instance ID for this configuration.

        Returns:
            Instance ID as UUID string
        """
        return self.instance_id


# Initialize the global config manager instance
config_manager = ConfigManager()
logger = config_manager.logger