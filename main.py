#!/usr/bin/env python3
import logging
import os
import sys
import asyncio
import argparse
import platform
import psutil
from colorama import Fore, Style
from config.config_manager import config_manager, logger
from core.performance import perf_tracker
from core.dev_assistant import DevAssistant
from cli.command_handler import CommandHandler

async def main(model: str = config_manager.get("default_model")):
    """Main application entry point with async support."""
    # Print welcome banner
    print(f"""
    {Fore.CYAN}╔═════════════════════════════════════════════════════════╗
    ║ {Fore.YELLOW}AI Development Assistant {config_manager.get('version', '2.0.0')}{Fore.CYAN}                          ║
    ║ {Fore.WHITE}An intelligent assistant for software development{Fore.CYAN}       ║
    ╚═════════════════════════════════════════════════════════╝{Style.RESET_ALL}
        """)

    # Check system information
    print(f"{Fore.GREEN}System Information:{Style.RESET_ALL}")
    print(f"  Python: {platform.python_version()} on {platform.system()} {platform.release()}")
    print(f"  CPU: {psutil.cpu_count(logical=False)} cores, {psutil.cpu_count()} threads")
    print(f"  Memory: {psutil.virtual_memory().total / (1024 ** 3):.1f} GB total\n")

    # Initialize components
    print(f"{Fore.GREEN}Initializing components...{Style.RESET_ALL}")

    dev_assistant = DevAssistant(model)
    command_handler = CommandHandler(dev_assistant)

    # Scan for existing projects
    await dev_assistant.project_manager.scan_projects()
    project_count = len(dev_assistant.project_manager.projects)
    print(f"  Found {project_count} existing projects")

    # Ensure cache directory exists
    os.makedirs(config_manager.get("cache_dir"), exist_ok=True)
    print(f"  Cache directory: {config_manager.get('cache_dir')}")

    # Check API connection
    print(f"  Checking API connection... ", end="")
    try:
        test_response = await dev_assistant.model_api.generate_response(
            model, "Hello, this is a connection test. Please respond with 'Connection successful'.", 0.0
        )
        if "Connection successful" in test_response or "success" in test_response.lower():
            print(f"{Fore.GREEN}Connected!{Style.RESET_ALL}")
        else:
            print(f"{Fore.YELLOW}Warning: Unexpected response{Style.RESET_ALL}")
    except Exception as e:
        print(f"{Fore.RED}Failed: {e}{Style.RESET_ALL}")
        logger.error(f"API connection test failed: {e}")

    print(f"\n{Fore.GREEN}Ready! Type :help for a list of commands.{Style.RESET_ALL}\n")

    # Main interaction loop
    while True:
        try:
            # Get user input with command completion
            user_input = input(f"{Fore.BLUE}>>> {Style.RESET_ALL}")

            if user_input.lower() == "exit":
                print("Exiting...")
                break

            # Parse and handle the command
            command_args = command_handler.parse_command(user_input)

            if not command_args:
                continue

            # Check if this is a command or conversation
            if command_args[0].startswith(":"):
                command_result = await command_handler.handle_command(command_args)

                if command_result == ":exit":
                    print("Exiting...")
                    break

                if command_result:
                    print(command_result)
            else:
                # Treat as conversation
                dev_assistant.conversation.add_message("User", user_input)

                # Show a streaming response with progress indicator
                print(f"{Fore.GREEN}AI Assistant is thinking...{Style.RESET_ALL}")

                response_chunks = []

                async def handle_chunk(chunk):
                    response_chunks.append(chunk)
                    # To create a nice streaming effect, print the chunk directly
                    print(chunk, end="", flush=True)

                # Stream the response
                await dev_assistant.model_api.stream_response(
                    dev_assistant.model,
                    dev_assistant.conversation.get_full_history(),
                    handle_chunk
                )

                # Complete the response by adding a newline
                print("\n")

                # Add the complete response to the conversation history
                full_response = "".join(response_chunks)
                dev_assistant.conversation.add_message("Model", full_response)

        except KeyboardInterrupt:
            print("\nExiting...")
            break

        except Exception as e:
            print(f"{Fore.RED}Error: {e}{Style.RESET_ALL}")
            logger.error(f"Error in main loop: {e}", exc_info=True)

    # Clean-up
    print("Saving conversation history...")
    dev_assistant.conversation.save_history()

    # Close API session
    print("Closing connections...")
    await dev_assistant.model_api.close()

    # Save final performance metrics
    if config_manager.get("enable_telemetry", False):
        metrics_file = os.path.join(config_manager.get("working_dir"), "metrics.json")
        with open(metrics_file, "w", encoding="utf-8") as f:
            json.dump(perf_tracker.get_metrics(), f, indent=2)
        print(f"Performance metrics saved to {metrics_file}")

    print(f"\n{Fore.GREEN}Thank you for using AI Development Assistant!{Style.RESET_ALL}")


if __name__ == "__main__":
    try:
        # Parse command line arguments
        parser = argparse.ArgumentParser(description="AI Development Assistant")
        parser.add_argument("--model", type=str, default=config_manager.get("default_model"),
                            help="Model to use for AI assistance")
        parser.add_argument("--config", type=str, default="ai_dev_config.json",
                            help="Path to configuration file")
        parser.add_argument("--working-dir", type=str, default=None,
                            help="Working directory for projects")
        parser.add_argument("--no-git", action="store_true",
                            help="Disable Git integration")
        parser.add_argument("--debug", action="store_true",
                            help="Enable debug logging")
        parser.add_argument("--web", action="store_true",
                            help="Start with web interface")
        parser.add_argument("--port", type=int, default=config_manager.get("web_interface_port", 8080),
                            help="Port for web interface")

        args = parser.parse_args()

        # Update configuration if command line args provided
        if args.working_dir:
            config_manager.set("working_dir", args.working_dir)

        if args.no_git:
            config_manager.set("git_integration", False)

        if args.debug:
            config_manager.set("log_level", "DEBUG")
            logger.setLevel(logging.DEBUG)

        if args.web:
            config_manager.set("enable_web_interface", True)
            config_manager.set("web_interface_port", args.port)

        # Handle special import requirements for aiohttp
        if config_manager.get("enable_web_interface", False):
            try:
                import aiohttp
                import socketio

                logger.info("Web interface dependencies found")
            except ImportError:
                logger.warning("Web interface dependencies not installed, disabling web interface")
                config_manager.set("enable_web_interface", False)
                print(
                    f"{Fore.YELLOW}Web interface dependencies not installed. Run: pip install aiohttp python-socketio{Style.RESET_ALL}")

        # Add proper handling of all imports
        try:
            import fnmatch  # Used in search_code function
            import psutil  # Used for system info
            import json    # Missing import
        except ImportError as e:
            logger.warning(f"Optional dependency not found: {e}")
            print(f"{Fore.YELLOW}Optional dependency not found: {e}. Some features may be limited.{Style.RESET_ALL}")

        # Run the async main function
        asyncio.run(main(args.model))
        logger.info("Application exited normally")

    except KeyboardInterrupt:
        print(f"\n{Fore.CYAN}Application terminated by user{Style.RESET_ALL}")
        logger.info("Application terminated by user")

    except Exception as e:
        logger.critical(f"Fatal error in main: {e}", exc_info=True)
        print(f"{Fore.RED}Fatal error: {e}{Style.RESET_ALL}")
        print(f"{Fore.RED}See log file for details{Style.RESET_ALL}")
        sys.exit(1)