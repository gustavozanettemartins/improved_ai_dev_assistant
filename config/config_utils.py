#!/usr/bin/env python3

import os
import json
import time
import logging
from typing import Dict, Any, List, Optional, Tuple
import inquirer
from colorama import Fore, Style

from config.config_manager import config_manager, logger, DEFAULT_CONFIG


# Note: You'll need to install the inquirer package:
# pip install inquirer


class ConfigWizard:
    """
    Interactive wizard for setting up and modifying configuration.

    This class provides a user-friendly interface for configuring the AI Dev Assistant,
    guiding users through the various configuration options with helpful explanations.
    """

    def __init__(self):
        """Initialize the configuration wizard."""
        self.logger = logger
        self.current_config = config_manager.get_all()

    def run(self) -> bool:
        """
        Run the configuration wizard interactively.

        Returns:
            True if the configuration was updated, False otherwise
        """
        try:
            print(f"\n{Fore.CYAN}===== AI Development Assistant Configuration Wizard ====={Style.RESET_ALL}\n")
            print("This wizard will help you set up your AI Development Assistant configuration.")
            print("Press Ctrl+C at any time to cancel without saving changes.\n")

            # Welcome and introduction
            proceed = inquirer.confirm("Would you like to proceed with the configuration?", default=True)
            if not proceed:
                print("\nConfiguration wizard cancelled. No changes were made.")
                return False

            # Start configuring different sections
            self._configure_basic_settings()
            self._configure_model_settings()
            self._configure_project_settings()
            self._configure_logging()
            self._configure_advanced_settings()

            # Final confirmation
            print(f"\n{Fore.GREEN}Configuration complete!{Style.RESET_ALL}")
            save = inquirer.confirm("Would you like to save these changes?", default=True)

            if save:
                # Update the config manager
                for key, value in self.current_config.items():
                    config_manager.set(key, value)

                # Save to file
                config_manager.save_config()
                self.logger.info("Configuration updated via wizard")
                print(f"\n{Fore.GREEN}Configuration saved successfully!{Style.RESET_ALL}")
                return True
            else:
                print("\nConfiguration changes discarded.")
                return False

        except KeyboardInterrupt:
            print(f"\n\n{Fore.YELLOW}Configuration wizard cancelled. No changes were made.{Style.RESET_ALL}")
            return False
        except Exception as e:
            self.logger.error(f"Error in configuration wizard: {e}")
            print(f"\n{Fore.RED}An error occurred during configuration: {e}{Style.RESET_ALL}")
            print("No changes were saved.")
            return False

    def _configure_basic_settings(self) -> None:
        """Configure basic application settings."""
        print(f"\n{Fore.CYAN}Basic Settings{Style.RESET_ALL}")

        # API URL
        api_url = inquirer.text(
            "API URL",
            default=self.current_config.get("api_url", DEFAULT_CONFIG["api_url"])
        )
        self.current_config["api_url"] = api_url

        # API Key (if needed)
        has_key = inquirer.confirm("Does your API require an authentication key?", default=False)
        if has_key:
            api_key = inquirer.password("API Key (input will be hidden)")
            self.current_config["api_key"] = api_key
        else:
            # Remove API key if it exists
            self.current_config.pop("api_key", None)

        # Working directory
        working_dir = inquirer.text(
            "Working directory for projects",
            default=self.current_config.get("working_dir", DEFAULT_CONFIG["working_dir"])
        )
        self.current_config["working_dir"] = working_dir

        # Request timeout
        timeout = inquirer.text(
            "Request timeout (seconds)",
            default=str(self.current_config.get("timeout_seconds", DEFAULT_CONFIG["timeout_seconds"])),
            validate=lambda _, x: x.isdigit() and int(x) > 0
        )
        self.current_config["timeout_seconds"] = int(timeout)

    def _configure_model_settings(self) -> None:
        """Configure AI model settings."""
        print(f"\n{Fore.CYAN}Model Settings{Style.RESET_ALL}")

        # Available models
        current_models = self.current_config.get("models", DEFAULT_CONFIG["models"])

        # List existing models
        print("\nConfigured models:")
        for model_name, model_config in current_models.items():
            print(f"  - {model_name} (temperature: {model_config.get('temperature', 0.7)})")

        # Modify models
        modify_models = inquirer.confirm("Would you like to modify the model configuration?", default=False)
        if modify_models:
            self._modify_models()

        # Default model
        available_models = list(self.current_config.get("models", {}).keys())
        if available_models:
            default_model = inquirer.list_input(
                "Select the default model",
                choices=available_models,
                default=self.current_config.get("default_model")
            )
            self.current_config["default_model"] = default_model

    def _modify_models(self) -> None:
        """Modify the available models configuration."""
        models = self.current_config.get("models", {}).copy()

        while True:
            options = ["Add a new model", "Edit an existing model", "Remove a model", "Done"]
            action = inquirer.list_input("What would you like to do?", choices=options)

            if action == "Add a new model":
                model_name = inquirer.text("Model name (e.g., gpt-4, llama3, claude-3)")
                temperature = float(inquirer.text(
                    "Temperature (0.0-1.0)",
                    default="0.7",
                    validate=lambda _, x: x.replace(".", "", 1).isdigit() and 0 <= float(x) <= 1
                ))
                timeout = int(inquirer.text(
                    "Timeout in seconds",
                    default="60",
                    validate=lambda _, x: x.isdigit() and int(x) > 0
                ))

                models[model_name] = {
                    "temperature": temperature,
                    "timeout": timeout
                }
                print(f"{Fore.GREEN}Model {model_name} added.{Style.RESET_ALL}")

            elif action == "Edit an existing model":
                if not models:
                    print(f"{Fore.YELLOW}No models to edit.{Style.RESET_ALL}")
                    continue

                model_name = inquirer.list_input("Select a model to edit", choices=list(models.keys()))
                temperature = float(inquirer.text(
                    "Temperature (0.0-1.0)",
                    default=str(models[model_name].get("temperature", 0.7)),
                    validate=lambda _, x: x.replace(".", "", 1).isdigit() and 0 <= float(x) <= 1
                ))
                timeout = int(inquirer.text(
                    "Timeout in seconds",
                    default=str(models[model_name].get("timeout", 60)),
                    validate=lambda _, x: x.isdigit() and int(x) > 0
                ))

                models[model_name] = {
                    "temperature": temperature,
                    "timeout": timeout
                }
                print(f"{Fore.GREEN}Model {model_name} updated.{Style.RESET_ALL}")

            elif action == "Remove a model":
                if not models:
                    print(f"{Fore.YELLOW}No models to remove.{Style.RESET_ALL}")
                    continue

                model_name = inquirer.list_input("Select a model to remove", choices=list(models.keys()))
                confirm = inquirer.confirm(f"Are you sure you want to remove {model_name}?", default=False)
                if confirm:
                    del models[model_name]
                    print(f"{Fore.GREEN}Model {model_name} removed.{Style.RESET_ALL}")

            elif action == "Done":
                break

        self.current_config["models"] = models

    def _configure_project_settings(self) -> None:
        """Configure project-related settings."""
        print(f"\n{Fore.CYAN}Project Settings{Style.RESET_ALL}")

        # Git integration
        git_integration = inquirer.confirm(
            "Enable Git integration for projects?",
            default=self.current_config.get("git_integration", DEFAULT_CONFIG["git_integration"])
        )
        self.current_config["git_integration"] = git_integration

        # Backup files
        backup_files = inquirer.confirm(
            "Create backups before modifying files?",
            default=self.current_config.get("backup_files", DEFAULT_CONFIG["backup_files"])
        )
        self.current_config["backup_files"] = backup_files

        # Max context files
        max_context_files = inquirer.text(
            "Maximum number of context files",
            default=str(self.current_config.get("max_context_files", DEFAULT_CONFIG["max_context_files"])),
            validate=lambda _, x: x.isdigit() and int(x) > 0
        )
        self.current_config["max_context_files"] = int(max_context_files)

    def _configure_logging(self) -> None:
        """Configure logging settings."""
        print(f"\n{Fore.CYAN}Logging Settings{Style.RESET_ALL}")

        logging_config = self.current_config.get("logging", {}).copy()

        # Console log level
        console_level_choices = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        console_level = inquirer.list_input(
            "Console log level",
            choices=console_level_choices,
            default=logging_config.get("console_level", "INFO")
        )
        logging_config["console_level"] = console_level

        # File log level
        file_level = inquirer.list_input(
            "File log level",
            choices=console_level_choices,
            default=logging_config.get("file_level", "DEBUG")
        )
        logging_config["file_level"] = file_level

        # JSON logs
        enable_json_logs = inquirer.confirm(
            "Enable structured JSON logs? (useful for log analysis)",
            default=logging_config.get("enable_json_logs", True)
        )
        logging_config["enable_json_logs"] = enable_json_logs

        # Log file size
        max_log_file_size = inquirer.text(
            "Maximum log file size (MB)",
            default=str(logging_config.get("max_log_file_size_mb", 10)),
            validate=lambda _, x: x.isdigit() and int(x) > 0
        )
        logging_config["max_log_file_size_mb"] = int(max_log_file_size)

        # Console colors
        use_console_colors = inquirer.confirm(
            "Use colors in console output?",
            default=logging_config.get("use_console_colors", True)
        )
        logging_config["use_console_colors"] = use_console_colors

        self.current_config["logging"] = logging_config

    def _configure_advanced_settings(self) -> None:
        """Configure advanced settings."""
        configure_advanced = inquirer.confirm("Would you like to configure advanced settings?", default=False)
        if not configure_advanced:
            return

        print(f"\n{Fore.CYAN}Advanced Settings{Style.RESET_ALL}")

        # Max history entries
        max_history = inquirer.text(
            "Maximum conversation history entries",
            default=str(self.current_config.get("max_history_entries", DEFAULT_CONFIG["max_history_entries"])),
            validate=lambda _, x: x.isdigit() and int(x) > 0
        )
        self.current_config["max_history_entries"] = int(max_history)

        # Cache settings
        enable_cache = inquirer.confirm(
            "Enable response caching?",
            default=True
        )

        if enable_cache:
            cache_dir = inquirer.text(
                "Cache directory",
                default=self.current_config.get("cache_dir", DEFAULT_CONFIG["cache_dir"])
            )
            self.current_config["cache_dir"] = cache_dir

            max_cache_size = inquirer.text(
                "Maximum cache size (MB)",
                default=str(self.current_config.get("max_cache_size_mb", DEFAULT_CONFIG["max_cache_size_mb"])),
                validate=lambda _, x: x.isdigit() and int(x) > 0
            )
            self.current_config["max_cache_size_mb"] = int(max_cache_size)
        else:
            # Disable cache by setting size to 0
            self.current_config["max_cache_size_mb"] = 0

        # Web interface
        enable_web = inquirer.confirm(
            "Enable web interface?",
            default=self.current_config.get("enable_web_interface", DEFAULT_CONFIG["enable_web_interface"])
        )
        self.current_config["enable_web_interface"] = enable_web

        if enable_web:
            web_port = inquirer.text(
                "Web interface port",
                default=str(self.current_config.get("web_interface_port", DEFAULT_CONFIG["web_interface_port"])),
                validate=lambda _, x: x.isdigit() and 1024 <= int(x) <= 65535
            )
            self.current_config["web_interface_port"] = int(web_port)


class ConfigMigrationUtil:
    """
    Utility for migrating configuration files between versions.

    This class handles the migration of configuration settings as the
    application evolves, ensuring backward compatibility and smooth upgrades.
    """

    def __init__(self):
        """Initialize the configuration migration utility."""
        self.logger = logger

    def migrate_config(self, config_file: str) -> Tuple[bool, str]:
        """
        Migrate a configuration file to the current version.

        Args:
            config_file: Path to the configuration file to migrate

        Returns:
            Tuple of (success, message)
        """
        try:
            if not os.path.exists(config_file):
                return False, f"Configuration file not found: {config_file}"

            # Load the config file
            with open(config_file, 'r', encoding='utf-8') as f:
                old_config = json.load(f)

            # Determine the version (if any)
            config_version = old_config.get("version", "1.0.0")

            # Perform migrations based on version
            migrated_config = self._apply_migrations(old_config, config_version)

            # Create a backup of the original file
            backup_file = f"{config_file}.{int(time.time())}.bak"
            with open(backup_file, 'w', encoding='utf-8') as f:
                json.dump(old_config, f, indent=2)

            # Write the migrated config back to the original file
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(migrated_config, f, indent=2)

            self.logger.info(f"Migrated configuration from version {config_version} to current version")
            return True, f"Successfully migrated configuration. Backup saved to {backup_file}"

        except json.JSONDecodeError as e:
            error_msg = f"Invalid JSON in configuration file: {e}"
            self.logger.error(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"Error migrating configuration: {e}"
            self.logger.error(error_msg)
            return False, error_msg

    def _apply_migrations(self, config: Dict[str, Any], version: str) -> Dict[str, Any]:
        """
        Apply migrations to the configuration based on its version.

        Args:
            config: Original configuration dictionary
            version: Current version of the configuration

        Returns:
            Migrated configuration dictionary
        """
        # Create a copy to avoid modifying the original during migration
        migrated = config.copy()

        # Always set the latest version
        migrated["version"] = "2.0.0"  # Update this as needed

        # Apply migrations in sequence based on version
        if self._version_less_than(version, "1.5.0"):
            migrated = self._migrate_pre_1_5_to_1_5(migrated)

        if self._version_less_than(version, "2.0.0"):
            migrated = self._migrate_1_5_to_2_0(migrated)

        return migrated

    def _version_less_than(self, version: str, target: str) -> bool:
        """
        Check if a version is less than a target version.

        Args:
            version: Version to check
            target: Target version to compare against

        Returns:
            True if version is less than target, False otherwise
        """
        try:
            version_parts = [int(x) for x in version.split('.')]
            target_parts = [int(x) for x in target.split('.')]

            # Pad with zeros if needed
            while len(version_parts) < 3:
                version_parts.append(0)
            while len(target_parts) < 3:
                target_parts.append(0)

            # Compare version parts
            for v, t in zip(version_parts, target_parts):
                if v < t:
                    return True
                elif v > t:
                    return False
            return False  # Equal versions
        except ValueError:
            # If we can't parse the version, assume it's older
            return True

    def _migrate_pre_1_5_to_1_5(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Migrate configuration from pre-1.5.0 to 1.5.0.

        Args:
            config: Configuration to migrate

        Returns:
            Migrated configuration
        """
        # Ensure models are in the new format
        if "models" in config and isinstance(config["models"], list):
            # Convert from list to dictionary format
            models_dict = {}
            for model in config["models"]:
                if isinstance(model, str):
                    models_dict[model] = {"temperature": 0.7, "timeout": 60}
                elif isinstance(model, dict) and "name" in model:
                    models_dict[model["name"]] = {
                        "temperature": model.get("temperature", 0.7),
                        "timeout": model.get("timeout", 60)
                    }
            config["models"] = models_dict

        # Ensure default_model is set and valid
        if "default_model" not in config or config["default_model"] not in config.get("models", {}):
            config["default_model"] = next(iter(config.get("models", {"model": {}}).keys()))

        # Ensure log_level is migrated to logging structure
        if "log_level" in config:
            log_level = config.pop("log_level")
            if "logging" not in config:
                config["logging"] = {}
            config["logging"]["console_level"] = log_level
            config["logging"]["file_level"] = "DEBUG"

        return config

    def _migrate_1_5_to_2_0(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Migrate configuration from 1.5.0 to 2.0.0.

        Args:
            config: Configuration to migrate

        Returns:
            Migrated configuration
        """
        # Ensure the logging structure is complete
        if "logging" not in config:
            config["logging"] = DEFAULT_CONFIG["logging"]
        else:
            # Ensure all logging keys are present
            for key, value in DEFAULT_CONFIG["logging"].items():
                if key not in config["logging"]:
                    config["logging"][key] = value

        # Ensure the error_handling structure is present
        if "error_handling" not in config:
            config["error_handling"] = DEFAULT_CONFIG["error_handling"]

        # Add any new configuration keys from DEFAULT_CONFIG
        for key, value in DEFAULT_CONFIG.items():
            if key not in config and key not in ["logging", "error_handling", "models"]:
                config[key] = value

        return config