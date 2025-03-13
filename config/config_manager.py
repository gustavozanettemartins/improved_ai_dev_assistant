#!/usr/bin/env python3

import json
import os
import logging
import uuid
from typing import Dict, Any, List

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
    # New configuration settings for structured logging and error handling
    "logging": {
        "app_name": "ai_dev_assistant",
        "console_level": "INFO",
        "file_level": "DEBUG",
        "enable_json_logs": True,
        "max_log_file_size_mb": 10,
        "backup_count": 5,
        "use_console_colors": True
    },
    "error_handling": {
        "default_error_mode": "log_and_raise",  # Options: log_only, log_and_raise, suppress
        "default_error_category": "unknown",  # Default error category if not specified
        "enable_error_suggestion": True,  # Provide suggestions for errors
        "max_retry_count": 3  # Maximum retry count for retryable operations
    }
}


# Set up basic logging first (this will be replaced with structured logging later)
def _setup_basic_logging():
    """Set up basic logging until structured logging is initialized."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler()]
    )
    return logging.getLogger("ConfigManager")


# Create a basic logger
logger = _setup_basic_logging()


class ConfigError(Exception):
    """Exception raised for configuration errors."""
    pass


class ConfigManager:
    """Manages configuration settings with file I/O and validation."""

    def __init__(self, config_file: str = "ai_dev_config.json"):
        """
        Initialize the configuration manager.

        Args:
            config_file: Path to the configuration file
        """
        self.config_file = config_file
        self.instance_id = str(uuid.uuid4())

        # Load configuration (the base config will be initialized here)
        self.config = self._load_config()

        # Create required directories
        self._ensure_directories()

        # Store original config paths for potential overwrites
        self._config_paths = {
            "user_config": self.config_file,
            "working_dir": self.config.get("working_dir", "projects")
        }

        logger.info(f"ConfigManager initialized with file: {self.config_file}")

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
                    logger.info(f"Loaded user configuration from {self.config_file}")

                    # Deep merge with defaults
                    config = DEFAULT_CONFIG.copy()
                    self._deep_update(config, user_config)
                    return config

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in config file: {e}, using defaults")
        except Exception as e:
            logger.error(f"Error loading config: {e}, using defaults")

        logger.warning("Using default configuration")
        return DEFAULT_CONFIG.copy()

    def _validate_config(self) -> List[str]:
        """
        Validate the configuration settings.

        Returns:
            List of validation errors, empty if valid
        """
        errors = []

        # Check required settings
        required_keys = ["api_url", "working_dir", "history_file", "default_model"]
        for key in required_keys:
            if key not in self.config:
                errors.append(f"Missing required config key: {key}")

        # Check and normalize numeric values
        if not isinstance(self.config.get("max_history_entries", 0), int):
            errors.append("max_history_entries must be an integer")

        # Validate URLs
        if "api_url" in self.config and not self.config["api_url"].startswith(("http://", "https://")):
            errors.append(f"Invalid API URL: {self.config['api_url']}")

        # Validate model settings
        if "models" in self.config and not isinstance(self.config["models"], dict):
            errors.append("'models' must be a dictionary")
        elif "models" in self.config:
            for model_name, settings in self.config["models"].items():
                if not isinstance(settings, dict):
                    errors.append(f"Model settings for {model_name} must be a dictionary")

        # Check if default model exists
        if "default_model" in self.config and "models" in self.config:
            if self.config["default_model"] not in self.config["models"]:
                errors.append(f"Default model {self.config['default_model']} not found in models")

        # Validate logging settings
        if "logging" in self.config:
            logging_config = self.config["logging"]

            if "console_level" in logging_config:
                level = logging_config["console_level"].upper()
                if level not in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
                    errors.append(f"Invalid console_level: {level}")

            if "file_level" in logging_config:
                level = logging_config["file_level"].upper()
                if level not in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
                    errors.append(f"Invalid file_level: {level}")

        return errors

    def _ensure_directories(self) -> None:
        """Ensure required directories exist."""
        dirs = [
            self.config["working_dir"],
            os.path.join(self.config["working_dir"], "templates"),
            self.config["cache_dir"],
            os.path.join(self.config["working_dir"], "logs"),
        ]

        for d in dirs:
            os.makedirs(d, exist_ok=True)
            logger.debug(f"Ensured directory exists: {d}")

    def save_config(self) -> None:
        """Save current configuration to file."""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2)
            logger.info(f"Configuration saved to {self.config_file}")
        except Exception as e:
            logger.error(f"Error saving config: {e}")
            raise ConfigError(f"Failed to save configuration: {e}")

    def get(self, key: str, default=None):
        """
        Get a configuration value.

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
                if part in current:
                    current = current[part]
                else:
                    return default
            return current

        return self.config.get(key, default)

    def set(self, key: str, value) -> None:
        """
        Set a configuration value.

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

        logger.debug(f"Config updated: {key} = {value}")

    def print_config(self) -> None:
        """Print current configuration in a user-friendly format."""
        try:
            import colorama
            from colorama import Fore, Style
            colorama.init()

            print(f"\n{Fore.CYAN}===== Current Configuration ====={Style.RESET_ALL}")
            self._print_dict_colored(self.config)

        except ImportError:
            print("\n===== Current Configuration =====")
            import pprint
            pprint.pprint(self.config)

    def _print_dict_colored(self, d: Dict, indent: int = 0) -> None:
        """
        Print a dictionary with colors and indentation.

        Args:
            d: Dictionary to print
            indent: Indentation level
        """
        from colorama import Fore, Style

        indent_str = "  " * indent
        for key, value in d.items():
            if isinstance(value, dict):
                print(f"{indent_str}{Fore.GREEN}{key}:{Style.RESET_ALL}")
                self._print_dict_colored(value, indent + 1)
            else:
                print(f"{indent_str}{Fore.GREEN}{key}:{Style.RESET_ALL} {value}")

    def validate(self) -> bool:
        """
        Validate the current configuration.

        Returns:
            True if configuration is valid, False otherwise
        """
        errors = self._validate_config()

        if errors:
            for error in errors:
                logger.error(f"Configuration error: {error}")
            return False

        return True

    def setup_structured_logging(self) -> None:
        """
        Set up structured logging based on configuration.

        This method should be called after the basic configuration has been loaded.
        """
        # Import here to avoid circular imports
        try:
            from utils.structured_logger import setup_structured_logging

            # Get logging configuration
            logging_config = self.config.get("logging", {})

            # Set up structured logging
            setup_structured_logging(
                app_name=logging_config.get("app_name", "ai_dev_assistant"),
                log_dir=os.path.join(self.config["working_dir"], "logs"),
                console_level=self._get_log_level(logging_config.get("console_level", "INFO")),
                file_level=self._get_log_level(logging_config.get("file_level", "DEBUG")),
                enable_json_logs=logging_config.get("enable_json_logs", True),
                max_log_file_size=logging_config.get("max_log_file_size_mb", 10) * 1024 * 1024,
                backup_count=logging_config.get("backup_count", 5),
                use_console_colors=logging_config.get("use_console_colors", True)
            )

            # Re-acquire the logger with structured logging
            global logger
            from utils.structured_logger import get_logger
            logger = get_logger("ConfigManager")

            logger.info(
                "Structured logging initialized",
                extra={"structured_data": {"config_id": self.instance_id}}
            )

        except ImportError:
            logger.warning("Structured logging not available, using basic logging")

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

    def get_instance_id(self) -> str:
        """
        Get the unique instance ID for this configuration.

        Returns:
            Instance ID as UUID string
        """
        return self.instance_id

    def reset(self) -> None:
        """Reset configuration to defaults."""
        self.config = DEFAULT_CONFIG.copy()
        logger.info("Configuration reset to defaults")

    def get_all(self) -> Dict[str, Any]:
        """
        Get the complete configuration dictionary.

        Returns:
            Copy of the configuration dictionary
        """
        return self.config.copy()


# Initialize the global config manager instance
config_manager = ConfigManager()